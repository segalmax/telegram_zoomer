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

async def post_test_message(tg_client):
    """Post a test message to the test source channel"""
    test_message = "Test message from e2e test: " + str(uuid.uuid4())
    
    try:
        logger.info(f"Posting test message to {TEST_SRC_CHANNEL}")
        await tg_client.send_message(TEST_SRC_CHANNEL, test_message)
        logger.info("Test message posted successfully")
        return True
    except Exception as e:
        logger.error(f"Error posting test message: {str(e)}")
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
        result = await post_test_message(tg_client)
        if result:
            logger.info("✅ E2E test passed - message posted successfully")
        else:
            logger.error("❌ E2E test failed - could not post message")
            
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