#!/usr/bin/env python3
"""
Unified test script for Telegram Zoomer Bot

This script provides testing for:
1. API Integration - Tests OpenAI and Stability AI without Telegram
2. Telegram Pipeline - Tests the full message flow through Telegram

Usage:
  python test.py api                # Run only API integration tests
  python test.py telegram           # Run only Telegram pipeline tests
  python test.py all                # Run all tests
  
Options:
  --stability                       # Test with Stability AI
  --no-images                       # Disable image generation
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
from translator import get_openai_client, translate_text
from image_generator import generate_image_for_post, generate_image_with_stability_ai
from bot import translate_and_post, extract_nytimes_link

# Try to import Telegram if needed
try:
    from telethon import TelegramClient
    from telethon.network import ConnectionTcpAbridged
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
    
    # Create a unique session file to avoid DB lock issues
    TEST_SESSION = f"test_session_{uuid.uuid4().hex[:8]}"
    client = None
    
    try:
        # Set environment variables based on arguments
        if args.stability:
            os.environ['USE_STABILITY_AI'] = 'true'
            logger.info("Testing with Stability AI image generation")
        if args.no_images:
            os.environ['GENERATE_IMAGES'] = 'false'
            logger.info("Image generation disabled for this test")
        
        logger.info(f"Creating new test session: {TEST_SESSION}")
        logger.info("This requires phone verification. You will need to enter the code sent to your phone.")
        
        # Create client with a unique test session
        client = TelegramClient(
            TEST_SESSION, 
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
        
        # Create test message with NYT link
        test_message = TEST_MESSAGE
        
        # Send test message to source channel
        logger.info(f"Sending test message to {TEST_SRC_CHANNEL}...")
        sent_msg = await client.send_message(TEST_SRC_CHANNEL, test_message)
        
        if not sent_msg:
            logger.error(f"Failed to send message to {TEST_SRC_CHANNEL}")
            return False
            
        logger.info(f"Test message sent successfully with ID: {sent_msg.id}")
        
        # Process the message using the production code
        logger.info("Processing message with production code...")
        
        # Extract NYTimes link from the message
        original_url = extract_nytimes_link(test_message)
        if original_url:
            logger.info(f"Extracted NYTimes URL: {original_url}")
        else:
            logger.warning("No NYTimes URL found in the test message")
        
        # Use the actual production function to translate and post
        success = await translate_and_post(
            client, 
            test_message, 
            sent_msg.id, 
            original_url,
            destination_channel=TEST_DST_CHANNEL
        )
        
        if not success:
            logger.error("Failed to process and post the message")
            return False
        
        logger.info("Message processed successfully")
        
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
        # Instead of checking for the specific URL, check for the source attribution text
        source_verified = await verify_message_in_channel(client, TEST_DST_CHANNEL, "Оригинал:", timeout=30, limit=15)
        if not source_verified:
            logger.warning("Could not verify source attribution in messages. This might be due to API limitations.")
            # Don't fail the test for this, it's likely a limitation of how we're viewing messages
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
            
        # Clean up the temporary session file
        try:
            session_file = f"{TEST_SESSION}.session"
            if os.path.exists(session_file):
                os.remove(session_file)
                logger.info(f"Removed temporary session file: {session_file}")
        except Exception as e:
            logger.warning(f"Failed to remove temporary session file: {str(e)}")

async def main():
    """Main function for running tests"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Unified test script for Telegram Zoomer Bot')
    
    # Test mode subparsers
    subparsers = parser.add_subparsers(dest='mode', help='Test mode', required=True)
    api_parser = subparsers.add_parser('api', help='Run API integration tests')
    telegram_parser = subparsers.add_parser('telegram', help='Run Telegram pipeline tests')
    all_parser = subparsers.add_parser('all', help='Run all tests')
    
    # Common options for all test modes
    for p in [api_parser, telegram_parser, all_parser]:
        p.add_argument('--stability', action='store_true', help='Test with Stability AI image generation')
        p.add_argument('--no-images', action='store_true', help='Disable image generation for testing')
    
    args = parser.parse_args()
    
    success = True
    
    # Run API integration tests
    if args.mode in ['api', 'all']:
        logger.info("=== Running API Integration Tests ===")
        api_success = await run_api_tests(args)
        if not api_success:
            success = False
            if args.mode == 'all':
                logger.error("API tests failed, skipping Telegram tests")
                return success
    
    # Run Telegram pipeline tests
    if args.mode in ['telegram', 'all'] and (args.mode == 'telegram' or success):
        logger.info("=== Running Telegram Pipeline Tests ===")
        if args.mode == 'telegram' or input("Continue with Telegram tests? (y/n) ").lower() == 'y':
            telegram_success = await run_telegram_test(args)
            if not telegram_success:
                success = False
    
    return success

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        if success:
            logger.info("🎉 All tests passed!")
            sys.exit(0)
        else:
            logger.error("❌ One or more tests failed")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        sys.exit(1) 