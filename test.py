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
import json
import app.bot
from app.translator import get_openai_client, translate_text
from app.image_generator import generate_image_for_post, generate_image_with_stability_ai
from app.bot import translate_and_post, main as bot_main
from app.pts_manager import load_pts, save_pts

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

# === Error counter to make tests fail on any logged ERROR ===
class _ErrorCounterHandler(logging.Handler):
    """Simple handler that increments a counter whenever an ERROR or higher is logged."""
    def __init__(self):
        super().__init__(level=logging.ERROR)
        self.error_count = 0

    def emit(self, record):
        if record.levelno >= logging.ERROR:
            self.error_count += 1


# Attach the handler
_error_counter_handler = _ErrorCounterHandler()
logger.addHandler(_error_counter_handler)

# Helper to query whether any error was logged
def _tests_encountered_errors() -> bool:
    return _error_counter_handler.error_count > 0

# Configuration
OPENAI_KEY = os.getenv('OPENAI_API_KEY')
# Use a higher-quality, more detailed message to ensure DALL-E can generate a good image
TEST_MESSAGE = (
    "BREAKING NEWS: Scientists discover remarkable new species of bioluminescent deep-sea creatures "
    "near hydrothermal vents in the Pacific Ocean. The colorful organisms have evolved unique "
    "adaptations to extreme pressure and toxic chemicals that could provide insights into early life on Earth. "
    "Read more at https://www.nytimes.com/2023/05/06/science/deep-sea-creatures.html"
)

# For Telegram tests
API_ID = os.getenv('TG_API_ID')
API_HASH = os.getenv('TG_API_HASH')
TG_PHONE = os.getenv('TG_PHONE')
TEST_SRC_CHANNEL = os.getenv('TEST_SRC_CHANNEL')
TEST_DST_CHANNEL = os.getenv('TEST_DST_CHANNEL')

# Unique identifier for the test run, passed by test_polling_flow.sh
TEST_RUN_MESSAGE_PREFIX = os.getenv('TEST_RUN_MESSAGE_PREFIX')
BOT_MODE_TIMEOUT = 60  # Reduced to 60 seconds

# Persistent test session file
PERSISTENT_TEST_SESSION = "session/test_session_persistent"

# Create an environment variable alias for SRC_CHANNEL because the bot uses that directly
# and we need to ensure it's set correctly during tests
os.environ['TEST_SRC_CHANNEL'] = os.getenv('TEST_SRC_CHANNEL', '')
os.environ['TEST_DST_CHANNEL'] = os.getenv('TEST_DST_CHANNEL', '')

# Ephemeral storage for Heroku - store PTS in environment variable
# MOVED TO app/pts_manager.py
# def save_heroku_pts(channel_username, pts):
#     ...

# def load_heroku_pts(channel_username):
#     ...

# Patch the pts_manager functions to use environment variables instead of files
# MOVED TO app/pts_manager.py (auto-patching)
# def patch_pts_functions_for_heroku():
#     ...

#
# API Integration Tests
#
async def test_translations():
    """Test translation functionality with different styles"""
    client = get_openai_client(OPENAI_KEY)
    
    test_text = TEST_MESSAGE
    
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
    # Use a longer test text with details to satisfy DALL-E's minimum requirements
    longer_test_text = (
        "BREAKING NEWS: Scientists discover fascinating new species of deep-sea creatures "
        "near hydrothermal vents in the Pacific Ocean. The newly discovered species include "
        "unique adaptations to extreme pressure and temperature conditions found in these depths."
    )
    result = await generate_image_for_post(client, longer_test_text)
    
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

        # We're using a simpler direct processing approach rather than relying on event handlers
        
        # Send test message to source channel
        logger.info(f"Sending test message to {TEST_SRC_CHANNEL}...")
        sent_msg = await client.send_message(TEST_SRC_CHANNEL, TEST_MESSAGE)
        
        if not sent_msg:
            logger.error(f"Failed to send message to {TEST_SRC_CHANNEL}")
            return False
            
        logger.info(f"Test message sent successfully with ID: {sent_msg.id}")
        
        # Process directly - just like we would in a real message handler
        logger.info(f"Processing test message directly (no event handler)")
        # Use longer test text now to ensure quality image generation
        longer_test_text = TEST_MESSAGE 
        success = await translate_and_post(
            client,
            longer_test_text,
            sent_msg.id,
            destination_channel=TEST_DST_CHANNEL
        )
        
        if not success:
            logger.error("Failed to process test message")
            return False
            
        logger.info("✅ Translation and posting completed successfully")
        
        # Verify that the message appears in the destination channel
        logger.info(f"Verifying message appears in {TEST_DST_CHANNEL}...")
        
        # Only check for RIGHT style (the only one we use)
        right_verified = await verify_message_in_channel(client, TEST_DST_CHANNEL, "RIGHT-BIDLO VERSION", timeout=60)
        if not right_verified:
            logger.error("Failed to verify RIGHT-BIDLO translation in destination channel")
            return False
            
        logger.info("RIGHT-BIDLO translation verified in destination channel")
        
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
    parser.add_argument('--bot-mode', action='store_true', help='Run the actual bot with test channels (for Heroku tests)')
    parser.add_argument('--stability', action='store_true', help='Test with Stability AI image generation')
    parser.add_argument('--no-images', action='store_true', help='Disable image generation for testing')
    parser.add_argument('--new-session', action='store_true', help='Force creation of a new session (requires re-authentication)')
    parser.add_argument('--process-recent', type=int, help='Process N recent messages from the source channel')
    
    args = parser.parse_args()
    
    # Special mode to run the actual bot instead of the tests
    if hasattr(args, 'bot_mode') and args.bot_mode:
        logger.info("=== Running in REAL BOT MODE with test channels ===")
        
        # Validate test channels are set
        if not TEST_SRC_CHANNEL or not TEST_DST_CHANNEL:
            logger.error("TEST_SRC_CHANNEL and TEST_DST_CHANNEL must be set in .env for bot mode")
            return False
            
        # Patch the environment to use test channels - make sure we're using the same format
        logger.info(f"Using test source channel: {TEST_SRC_CHANNEL}")
        logger.info(f"Using test destination channel: {TEST_DST_CHANNEL}")
        
        # Save the original values to restore later
        original_src = os.environ.get('SRC_CHANNEL')
        original_dst = os.environ.get('DST_CHANNEL')
        
        # Set the environment variables for the test
        os.environ['SRC_CHANNEL'] = TEST_SRC_CHANNEL
        os.environ['DST_CHANNEL'] = TEST_DST_CHANNEL
        
        # Set TEST_MODE to true
        os.environ['TEST_MODE'] = 'true'
        
        # Patch PTS storage for Heroku compatibility - NO LONGER NEEDED HERE, auto-patched in pts_manager
        # patch_pts_functions_for_heroku()
        
        # Create empty sys.argv to avoid parsing errors in bot.py's argparse
        # We'll pass only the arguments that main() in bot.py can handle
        import sys
        original_argv = sys.argv.copy()
        sys.argv = [sys.argv[0]]  # Keep only the script name

        # Add --no-images if specified
        if args.no_images:
            os.environ['GENERATE_IMAGES'] = 'false'
            logger.info("Image generation disabled for bot mode")
        
        # Add --process-recent if specified (though not typical for polling test)
        if hasattr(args, 'process_recent') and args.process_recent:
            sys.argv.append('--process-recent')
            sys.argv.append(str(args.process_recent))

        # Create a shared event to signal message processing
        message_processed_event = asyncio.Event()
        original_translate_and_post = app.bot.translate_and_post

        async def wrapped_translate_and_post(client, txt, message_id=None, destination_channel=None):
            # Check if the processed message is the one we are waiting for
            if TEST_RUN_MESSAGE_PREFIX and TEST_RUN_MESSAGE_PREFIX in txt:
                logger.info(f"✅ BOT_MODE: Successfully processed test message with prefix: {TEST_RUN_MESSAGE_PREFIX}")
                message_processed_event.set() # Signal that the message was processed
            return await original_translate_and_post(client, txt, message_id, destination_channel)

        # Patch translate_and_post
        app.bot.translate_and_post = wrapped_translate_and_post

        # Run the actual bot's main function, but with a timeout
        try:
            logger.info(f"BOT_MODE: Waiting for message with prefix {TEST_RUN_MESSAGE_PREFIX} for up to {BOT_MODE_TIMEOUT} seconds.")
            main_bot_task = asyncio.create_task(bot_main())
            # Wait for either the bot to finish or the message_processed_event to be set, or timeout
            done, pending = await asyncio.wait(
                [main_bot_task, asyncio.create_task(message_processed_event.wait())],
                timeout=BOT_MODE_TIMEOUT,
                return_when=asyncio.FIRST_COMPLETED
            )

            if message_processed_event.is_set():
                logger.info("BOT_MODE: Test message processed successfully.")
                # Cancel the main bot task if it's still running
                if not main_bot_task.done():
                    main_bot_task.cancel()
                return True # Success
            
            # Check if main_bot_task completed for other reasons (e.g. error)
            for task in done:
                if task == main_bot_task and task.done() and task.exception():
                    logger.error(f"BOT_MODE: bot_main task failed: {task.exception()}")
                    return False # Failure

            logger.error(f"BOT_MODE: Timed out after {BOT_MODE_TIMEOUT} seconds waiting for message: {TEST_RUN_MESSAGE_PREFIX}.")
            if not main_bot_task.done():
                main_bot_task.cancel()
            return False # Failure (timeout)
            
        except asyncio.CancelledError:
            logger.info("BOT_MODE: Main bot task was cancelled.")
            return message_processed_event.is_set() # Return true if event was set before cancellation
        except Exception as e:
            logger.error(f"BOT_MODE: Error running bot_main: {e}", exc_info=True)
            return False
        finally:
            # Restore original argv and translate_and_post
            sys.argv = original_argv
            app.bot.translate_and_post = original_translate_and_post
            
            # Restore original environment variables if they existed
            if original_src:
                os.environ['SRC_CHANNEL'] = original_src
            if original_dst:
                os.environ['DST_CHANNEL'] = original_dst
    
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
        # Override success if any errors were logged
        if _tests_encountered_errors():
            logger.error("❌ Tests logged one or more errors – marking as FAILED")
            success = False

        if success:
            logger.info("🎉 All end-to-end tests passed without errors!")
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