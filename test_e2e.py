#!/usr/bin/env python3
"""
End-to-end test script for Telegram Zoomer Bot with image generation

This script tests the whole flow from a test source channel to a destination channel.
First run test_core.py to verify translations before running this test.
"""

import os
import asyncio
import logging
import time
import uuid
from dotenv import load_dotenv
from telethon import TelegramClient, events

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration - using test channels instead of production ones
API_ID = int(os.getenv('TG_API_ID'))
API_HASH = os.getenv('TG_API_HASH')
TG_PHONE = os.getenv('TG_PHONE')
SESSION = f"test_session_{uuid.uuid4().hex[:8]}"  # Create unique session file for testing
TEST_SRC_CHANNEL = os.getenv('TEST_SRC_CHANNEL', 'nyttest')         # Test source channel
TEST_DST_CHANNEL = os.getenv('TEST_DST_CHANNEL', 'nytzoomerutest')  # Test destination channel
MAX_WAIT_TIME = 60  # Maximum time to wait for translation to appear in seconds

async def post_test_message(tg_client):
    """Post a test message to the test source channel"""
    test_id = str(uuid.uuid4())
    test_message = f"Test message from e2e test: {test_id}"
    
    try:
        logger.info(f"Posting test message to {TEST_SRC_CHANNEL}")
        await tg_client.send_message(TEST_SRC_CHANNEL, test_message)
        logger.info("Test message posted successfully")
        return test_id, True
    except Exception as e:
        logger.error(f"Error posting test message: {str(e)}")
        return None, False

async def check_destination_channel(tg_client, test_id, timeout=MAX_WAIT_TIME):
    """Check if test message appears in destination channel after translation"""
    logger.info(f"Waiting for translations to appear in {TEST_DST_CHANNEL} (max {timeout} seconds)...")
    
    start_time = time.time()
    found_translations = 0
    
    while time.time() - start_time < timeout:
        try:
            # Get recent messages from destination channel
            messages = await tg_client.get_messages(TEST_DST_CHANNEL, limit=10)
            
            # Check if any messages contain our test ID
            for msg in messages:
                if msg.text and test_id in msg.text:
                    found_translations += 1
                    logger.info(f"Found a translation with our test ID: {msg.text[:50]}...")
            
            # If we found both translations (LEFT and RIGHT styles), success!
            if found_translations >= 2:
                logger.info(f"✅ Found both translations in destination channel")
                return True
                
            # Wait before checking again
            await asyncio.sleep(5)
            
        except Exception as e:
            logger.error(f"Error checking destination channel: {str(e)}")
            await asyncio.sleep(5)
    
    # If we get here, we didn't find the expected translations
    if found_translations > 0:
        logger.warning(f"Found {found_translations} translation(s), but expected at least 2")
    else:
        logger.error("No translations found in destination channel")
    
    return False

async def main():
    """Main test function"""
    logger.info("Starting end-to-end test")
    
    # Verify required environment variables
    if not all([API_ID, API_HASH, TG_PHONE, TEST_SRC_CHANNEL, TEST_DST_CHANNEL]):
        logger.error("Missing required environment variables")
        return
    
    # Create client with unique session
    tg_client = TelegramClient(SESSION, API_ID, API_HASH)
    
    try:
        # Start from scratch with a new session
        await tg_client.start(phone=TG_PHONE)
        logger.info("Telegram client connected and authenticated")
        
        # Post a test message
        test_id, post_result = await post_test_message(tg_client)
        if not post_result:
            logger.error("❌ E2E test failed - could not post message")
            return
            
        # Now check if the message appears in the destination channel
        translations_result = await check_destination_channel(tg_client, test_id)
        
        if translations_result:
            logger.info("✅ E2E test fully passed - message was translated and posted to destination")
        else:
            logger.error("❌ E2E test partially failed - message posted but translations not found")
            
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
    finally:
        await tg_client.disconnect()
        logger.info("Test cleanup complete, session file will be automatically removed")
        # Remove the temporary session file
        try:
            os.remove(f"{SESSION}.session")
            logger.info(f"Removed temporary session file")
        except (FileNotFoundError, PermissionError, OSError) as e:
            logger.debug(f"Could not remove session file: {e}")

if __name__ == "__main__":
    logger.info("Note: This test requires interactive authentication.")
    logger.info("If you don't want to authenticate, use test_core.py instead.")
    input("Press Enter to continue with the test (or Ctrl+C to cancel)...")
    asyncio.run(main()) 