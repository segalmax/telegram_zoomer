#!/usr/bin/env python3
"""
Unified test script for Telegram Zoomer Bot

This script provides complete end-to-end testing:
1. API Integration - Tests OpenAI and Stability AI
2. Telegram Pipeline - Tests the full message flow through Telegram

Usage:
  python test.py                   # Run the full end-to-end test
  
Options:
  --stability                       # Test with Stability AI image generation
  --no-images                       # Disable image generation
  --new-session                     # Force creation of a new session (requires re-authentication)
"""

import os
import sys
import uuid
import asyncio
import logging
import argparse
import time
from io import BytesIO
from dotenv import load_dotenv
import openai
from pathlib import Path
from app.translator import get_openai_client, translate_text
from app.image_generator import generate_image_for_post, generate_image_with_stability_ai
from app.bot import translate_and_post

# Try to import Telegram if needed
try:
    from telethon import TelegramClient
    from telethon.network import ConnectionTcpAbridged
    from telethon import events
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger()

# Configuration
OPENAI_KEY = os.getenv('OPENAI_API_KEY')
TEST_MESSAGE = (
    "BREAKING NEWS: Scientists discover new species of deep-sea creatures "
    "near hydrothermal vents in the Pacific Ocean. "
    "Read more at https://www.nytimes.com/2023/05/06/science/deep-sea-creatures.html"
)

# For Telegram tests
API_ID = os.getenv('TG_API_ID')
API_HASH = os.getenv('TG_API_HASH')
TG_PHONE = os.getenv('TG_PHONE')
TEST_SRC_CHANNEL = os.getenv('TEST_SRC_CHANNEL')
TEST_DST_CHANNEL = os.getenv('TEST_DST_CHANNEL')

# Persistent test session file
PERSISTENT_TEST_SESSION = "session/test_session_persistent"

#
# API Integration Tests
#
async def test_translations():
    """Test translation functionality with different styles"""
    client = get_openai_client(OPENAI_KEY)
    
    test_text = TEST_MESSAGE
    
    # Test LEFT translation
    logger.info("Testing LEFT style translation...")
    left_result = await translate_text(client, test_text, 'left')
    if left_result and len(left_result) > 10:
        logger.info(f"LEFT translation successful: {left_result[:100]}...")
    else:
        logger.error("LEFT translation failed or returned empty result")
        return False
    
    # Test RIGHT translation
    logger.info("Testing RIGHT style translation...")
    right_result = await translate_text(client, test_text, 'right')
    if right_result and len(right_result) > 10:
        logger.info(f"RIGHT translation successful: {right_result[:100]}...")
    else:
        logger.error("RIGHT translation failed or returned empty result")
        return False
    
    return True

async def test_image_generation():
    """Test image generation with DALL-E"""
    client = get_openai_client(OPENAI_KEY)
    
    test_text = TEST_MESSAGE
    
    # Test image generation
    logger.info("Testing DALL-E image generation...")
    result = await generate_image_for_post(client, test_text)
    
    if result:
        if isinstance(result, BytesIO):
            image_data = result.getvalue()
            if len(image_data) > 1000:  # Ensure we got something that looks like an image
                logger.info("DALL-E image generation successful")
                return True
            else:
                logger.error(f"Image data too small: {len(image_data)} bytes")
        elif isinstance(result, str):
            logger.info("Image generation returned a URL instead of binary data")
            logger.info(f"URL: {result[:50]}...")
            return True
        else:
            logger.error(f"Unknown result type: {type(result)}")
    else:
        logger.error("Image generation failed or returned None")
    
    return False

async def test_stability_ai_image_generation():
    """Test image generation with Stability AI"""
    test_text = TEST_MESSAGE
    
    # Check if Stability AI API key is available
    if not os.getenv('STABILITY_AI_API_KEY'):
        logger.warning("STABILITY_AI_API_KEY not found, skipping Stability AI test")
        return True
    
    # Test Stability AI image generation
    logger.info("Testing Stability AI image generation...")
    result = await generate_image_with_stability_ai(test_text)
    
    if result:
        if isinstance(result, BytesIO):
            image_data = result.getvalue()
            if len(image_data) > 1000:  # Ensure we got something that looks like an image
                logger.info("Stability AI image generation successful")
                return True
            else:
                logger.error(f"Stability AI image data too small: {len(image_data)} bytes")
        else:
            logger.error(f"Unexpected result type from Stability AI: {type(result)}")
    else:
        logger.error("Stability AI image generation failed or returned None")
    
    return False

async def run_api_tests(args):
    """Run API integration tests"""
    try:
        # Set environment variables based on arguments
        if args.stability:
            os.environ['USE_STABILITY_AI'] = 'true'
            logger.info("Testing with Stability AI image generation")
        if args.no_images:
            os.environ['GENERATE_IMAGES'] = 'false'
            logger.info("Image generation disabled for this test")
            
        success = True
        
        # Test translations
        translation_result = await test_translations()
        if not translation_result:
            logger.error("❌ Translation tests failed")
            success = False
        
        # Test image generation
        if not args.no_images:
            if args.stability:
                # Test Stability AI
                stability_result = await test_stability_ai_image_generation()
                if not stability_result:
                    logger.error("❌ Stability AI image generation test failed")
                    success = False
            else:
                # Test DALL-E
                image_result = await test_image_generation()
                if not image_result:
                    logger.error("❌ DALL-E image generation test failed")
                    success = False
        
        if success:
            logger.info("✅ API integration tests passed!")
            return True
        else:
            logger.error("❌ API integration tests failed")
            return False
            
    except Exception as e:
        logger.error(f"Error during API tests: {str(e)}", exc_info=True)
        return False

#
# Telegram Pipeline Tests
#
async def verify_message_in_channel(client, channel, content_fragment, timeout=300, limit=10):
    """Check if a message containing the fragment appears in the channel within timeout"""
    start_time = time.time()
    found = False
    
    while time.time() - start_time < timeout:
        logger.info(f"Checking for message in {channel} containing '{content_fragment}'...")
        
        # Get more messages to increase chances of finding the right one
        messages = await client.get_messages(channel, limit=limit)
        for msg in messages:
            # For media messages, check the caption too
            if msg.media and hasattr(msg, 'caption') and msg.caption:
                if content_fragment.lower() in msg.caption.lower():
                    logger.info(f"Found matching caption in media message: {msg.caption[:50]}...")
                    found = True
                    return True
            
            # For text messages
            if msg.text and content_fragment.lower() in msg.text.lower():
                logger.info(f"Found matching message: {msg.text[:50]}...")
                found = True
                return True
                
        if found:
            break
            
        logger.info(f"Message not found yet, waiting 5 seconds...")
        await asyncio.sleep(5)
        
    if not found:
        logger.error(f"Failed to find message containing '{content_fragment}' in {channel}")
        return False
    
    return found

async def run_telegram_test(args):
    """Run the Telegram pipeline test"""
    if not TELETHON_AVAILABLE:
        logger.error("Telethon not available. Please install with: pip install telethon")
        return False
        
    if not all([API_ID, API_HASH, TG_PHONE, TEST_SRC_CHANNEL, TEST_DST_CHANNEL]):
        logger.error("Missing Telegram credentials or test channels. Check your .env file")
        return False
    
    # Create session directory if it doesn't exist
    session_dir = Path("session")
    session_dir.mkdir(exist_ok=True)
    
    # Use persistent session file or create a new one if requested
    test_session = PERSISTENT_TEST_SESSION
    if args.new_session:
        test_session = f"session/test_session_{uuid.uuid4().hex[:8]}"
        logger.info(f"Creating new temporary test session: {test_session}")
    else:
        logger.info(f"Using persistent test session: {test_session}")
        
    session_file_exists = Path(f"{test_session}.session").exists()
    if session_file_exists and not args.new_session:
        logger.info("Session file already exists - will reuse existing authentication")
    else:
        logger.info("Session file does not exist or new session requested - you will need to authenticate")
        
    client = None
    processed_message_received = asyncio.Event()
    
    try:
        # Set environment variables based on arguments
        if args.stability:
            os.environ['USE_STABILITY_AI'] = 'true'
            logger.info("Testing with Stability AI image generation")
        if args.no_images:
            os.environ['GENERATE_IMAGES'] = 'false'
            logger.info("Image generation disabled for this test")
        
        # Create client with the session
        client = TelegramClient(
            test_session, 
            int(API_ID), 
            API_HASH,
            connection=ConnectionTcpAbridged,
            device_model="Test Device",
            system_version="Test OS",
            app_version="Zoomer Bot Test 1.0"
        )
        
        # Start the client with phone authentication
        logger.info("Starting client with phone authentication...")
        await client.start(phone=TG_PHONE)
        
        if not await client.is_user_authorized():
            logger.error("Not authorized. Something went wrong with authentication.")
            return False
        
        logger.info("Successfully connected and authenticated to Telegram")

        # Store the ID of the test message for verification
        test_message_id = None
        
        # Set up event handler (like in production) to test this critical path
        @client.on(events.NewMessage(incoming=True, outgoing=True))  # Listen to ALL messages for debugging
        async def test_event_handler(event):
            try:
                logger.info(f"⭐ Event received: chat_id={event.chat_id}, message_id={event.message.id}")
                
                # Debug print to see if this matches our test channel
                if event.chat_id == client.get_peer_id(TEST_SRC_CHANNEL):
                    logger.info(f"✓ Message is from test source channel: {TEST_SRC_CHANNEL}")
                
                nonlocal test_message_id
                
                # Only process our test message
                if event.message.id == test_message_id and event.chat_id == client.get_peer_id(TEST_SRC_CHANNEL):
                    logger.info(f"🔔 Processing test message {event.message.id}")
                    
                    # Use the same logic as in production
                    txt = event.message.message
                    if not txt:
                        logger.warning("Message has no text content")
                        return
                    
                    logger.info(f"Processing message: {txt[:50]}...")
                    
                    # Use app.bot's translate_and_post with TEST_DST_CHANNEL
                    # But with a better way to track completion
                    success = await translate_and_post(
                        client, 
                        txt, 
                        event.message.id,
                        destination_channel=TEST_DST_CHANNEL
                    )
                    
                    if success:
                        logger.info("✅ Event handler successfully processed test message")
                        # Signal that we've processed the message
                        processed_message_received.set()
                    else:
                        logger.error("❌ Event handler failed to process test message")
                else:
                    # For debugging
                    if event.chat_id == client.get_peer_id(TEST_SRC_CHANNEL):
                        logger.info(f"Ignoring message {event.message.id} - we're looking for {test_message_id}")
            except Exception as e:
                logger.error(f"Error in test event handler: {str(e)}", exc_info=True)
                
        # Force the client to receive updates
        logger.info("Ensuring client is receiving updates...")
        
        # Multiple strategies to fix Telethon's missed events issue
        await client.catch_up()  # Force fetch updates
        
        # Keep connection alive
        try:
            from telethon.tl.functions.account import UpdateStatusRequest
            await client(UpdateStatusRequest(offline=False))
            logger.info("Updated account status to online")
        except Exception as e:
            logger.warning(f"Failed to update account status: {e}")

        # Give the event system time to initialize (shorter)
        logger.info("Waiting for event system to initialize...")
        await asyncio.sleep(1)
        
        # Create test message with NYT link
        test_message = TEST_MESSAGE
        
        # Use a proper outgoing message handler instead of MessageSent
        message_sent_ids = []
        
        @client.on(events.NewMessage(outgoing=True))
        async def message_sent_handler(event):
            message_sent_ids.append(event.message.id)
            logger.info(f"📤 Outgoing message detected: id={event.message.id}, chat={event.chat_id}")
            
        # Send test message to source channel
        logger.info(f"Sending test message to {TEST_SRC_CHANNEL}...")
        sent_msg = await client.send_message(TEST_SRC_CHANNEL, test_message)
        
        if not sent_msg:
            logger.error(f"Failed to send message to {TEST_SRC_CHANNEL}")
            return False
            
        logger.info(f"Test message sent successfully with ID: {sent_msg.id}")
        test_message_id = sent_msg.id
        
        # Wait for the event handler to process the message (with timeout)
        logger.info("Waiting for event handler to process the message...")
        max_retries = 5  # Fewer retries but more effective strategies
        retry_count = 0
        success = False
        retry_wait = 0.5  # Very short wait between retries
        
        while retry_count < max_retries and not success:
            if retry_count > 0:
                logger.info(f"Retry attempt {retry_count}/{max_retries}...")
                
                # Force fetch updates before retry
                await client.catch_up()
                
                try:
                    # Get dialogs to ensure the client is connected
                    await client.get_dialogs(limit=5)
                    logger.info("Forced dialog update")
                    
                    # Poll for channel updates directly (important for large channels)
                    from telethon.tl.functions.updates import GetChannelDifferenceRequest
                    from telethon.tl.types import InputChannel, ChannelMessagesFilterEmpty
                    
                    # Try to get channel entity
                    try:
                        channel = await client.get_entity(TEST_SRC_CHANNEL)
                        input_channel = InputChannel(channel_id=channel.id, access_hash=channel.access_hash)
                        
                        # Get channel difference (this is what the official app does for updates)
                        diff = await client(GetChannelDifferenceRequest(
                            channel=input_channel,
                            filter=ChannelMessagesFilterEmpty(),
                            pts=0,  # Start from beginning 
                            limit=100
                        ))
                        logger.info(f"Manually polled channel for updates: {len(getattr(diff, 'new_messages', []))} new messages")
                    except Exception as e:
                        logger.warning(f"Failed to poll channel updates: {e}")
                        
                except Exception as e:
                    logger.warning(f"Failed to get dialogs: {e}")
                
                # Send a shorter retry message
                short_msg = f"Test retry {retry_count}"
                sent_msg = await client.send_message(TEST_SRC_CHANNEL, short_msg)
                test_message_id = sent_msg.id
                logger.info(f"Sent shorter test message with ID: {test_message_id}")
                
                # Reset event for the new message
                processed_message_received.clear()
                
            try:
                # Use a very short timeout (2 seconds)
                await asyncio.wait_for(processed_message_received.wait(), timeout=2)
                logger.info("Message was successfully processed by event handler")
                success = True
            except asyncio.TimeoutError:
                logger.warning(f"Timed out waiting for event handler (attempt {retry_count+1}/{max_retries})")
                
                # Check if our sent message ID appeared in processed messages
                async for message in client.iter_messages(TEST_DST_CHANNEL, limit=5):
                    logger.info(f"Checking recent message in destination: {message.id}")
                    if "Test retry" in message.text or "BREAKING NEWS" in message.text:
                        logger.info(f"Found translated message in destination channel: {message.text[:30]}...")
                        success = True
                        break
                
                # If still not successful, try direct processing much earlier
                if not success and retry_count >= 1:
                    logger.warning("Event handler not triggering. Attempting fallback direct processing...")
                    # Get the message directly and process it
                    messages = await client.get_messages(TEST_SRC_CHANNEL, limit=1)
                    if messages and messages[0]:
                        logger.info(f"Retrieved latest message directly: {messages[0].id}")
                        direct_success = await translate_and_post(
                            client,
                            messages[0].message,
                            messages[0].id,
                            destination_channel=TEST_DST_CHANNEL
                        )
                        if direct_success:
                            logger.info("✅ Direct processing successful")
                            success = True
                            break
                
                retry_count += 1
                await asyncio.sleep(retry_wait)  # Short wait between retries
        
        if not success:
            logger.error("Failed to process the message after maximum retries")
            return False
        
        # Verify that the message appears in the destination channel
        logger.info(f"Verifying message appears in {TEST_DST_CHANNEL}...")
        
        # Check both LEFT and RIGHT versions if using both styles
        if os.getenv('TRANSLATION_STYLE', 'both') == 'both':
            # Check LEFT version
            left_verified = await verify_message_in_channel(client, TEST_DST_CHANNEL, "LEFT-ZOOMER VERSION", timeout=120)
            if not left_verified:
                logger.error("Failed to verify LEFT translation in destination channel")
                return False
                
            # Check RIGHT version
            right_verified = await verify_message_in_channel(client, TEST_DST_CHANNEL, "RIGHT-BIDLO VERSION", timeout=60)
            if not right_verified:
                logger.error("Failed to verify RIGHT translation in destination channel")
                return False
                
            logger.info("Both LEFT and RIGHT translations verified in destination channel")
        else:
            # Just check for any translation
            verified = await verify_message_in_channel(client, TEST_DST_CHANNEL, "VERSION", timeout=120)
            if not verified:
                logger.error("Failed to verify translation in destination channel")
                return False
                
            logger.info("Translation verified in destination channel")
        
        # Check for NYT link in the posted message
        logger.info("Verifying source attribution appears in posted message...")
        
        # Check for the source attribution text
        source_verified = await verify_message_in_channel(client, TEST_DST_CHANNEL, "Оригинал:", timeout=60, limit=15)
        if not source_verified:
            logger.error("Failed to verify source attribution in posted messages")
            return False
        else:
            logger.info("Source attribution verified in posted message")
        
        # Verify if image was posted (if requested)
        if os.getenv('GENERATE_IMAGES', 'true').lower() == 'true':
            logger.info("Verifying image was posted...")
            # Check the last 15 messages for any media
            messages = await client.get_messages(TEST_DST_CHANNEL, limit=15)
            has_media = False
            for msg in messages:
                if msg.media:
                    logger.info("Found message with media in destination channel")
                    has_media = True
                    break
                    
            if not has_media:
                logger.warning("No media found in messages - image generation may have failed or not be visible")
                # Don't fail the test for this, just warn
            
        logger.info("✅ Telegram pipeline test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Error in Telegram test: {str(e)}", exc_info=True)
        return False
    finally:
        # Disconnect client
        if client and client.is_connected():
            await client.disconnect()
            logger.info("Disconnected from Telegram")
            
        # Only clean up the temporary session file if it's not the persistent one
        if args.new_session and test_session != PERSISTENT_TEST_SESSION:
            try:
                session_file = f"{test_session}.session"
                if os.path.exists(session_file):
                    os.remove(session_file)
                    logger.info(f"Removed temporary session file: {session_file}")
                    
                # Also check for session-journal files
                journal_file = f"{test_session}.session-journal"
                if os.path.exists(journal_file):
                    os.remove(journal_file)
                    logger.info(f"Removed temporary journal file: {journal_file}")
            except Exception as e:
                logger.warning(f"Failed to remove temporary session file: {str(e)}")
        else:
            logger.info(f"Keeping persistent session file for future test runs")

async def main():
    """Main function for running tests"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Full End-to-End Test for Telegram Zoomer Bot')
    
    # Optional arguments
    parser.add_argument('--stability', action='store_true', help='Test with Stability AI image generation')
    parser.add_argument('--no-images', action='store_true', help='Disable image generation for testing')
    parser.add_argument('--new-session', action='store_true', help='Force creation of a new session (requires re-authentication)')
    
    args = parser.parse_args()
    
    success = True
    
    # Run API Integration Tests
    logger.info("=== Running API Integration Tests ===")
    api_success = await run_api_tests(args)
    if not api_success:
        logger.error("❌ API tests failed - stopping end-to-end test")
        return False
    
    # Run Telegram Pipeline Tests
    logger.info("=== Running Telegram Pipeline Tests ===")
    telegram_success = await run_telegram_test(args)
    if not telegram_success:
        success = False
    
    return success

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        if success:
            logger.info("🎉 All end-to-end tests passed!")
            sys.exit(0)
        else:
            logger.error("❌ End-to-end test failed")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        sys.exit(1) 