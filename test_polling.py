#!/usr/bin/env python3
"""
Test Polling Mechanism

A simple helper script to test the bot's channel polling mechanism.
This script sends a test message to the test source channel and then
disconnects, letting the bot (running in a different process) detect
and process the message via polling.

Usage:
  python test_polling.py  # Send a test message to trigger polling
"""

import os
import sys
import asyncio
import logging
import time
import uuid
from pathlib import Path
from dotenv import load_dotenv

# Try to import Telegram
try:
    from telethon import TelegramClient
    from telethon.network import ConnectionTcpAbridged
except ImportError:
    print("Error: Telethon not available. Install with 'pip install telethon'.")
    sys.exit(1)

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
API_ID = os.getenv('TG_API_ID')
API_HASH = os.getenv('TG_API_HASH')
TG_PHONE = os.getenv('TG_PHONE')
TEST_SRC_CHANNEL = os.getenv('TEST_SRC_CHANNEL')
TEST_SESSION = os.getenv('TEST_SESSION', 'session/polling_test_session')
MESSAGE_PREFIX = "POLLING-TEST-"  # Prefix to identify test messages

# Define a random test message
TEST_MESSAGE = f"{MESSAGE_PREFIX}{uuid.uuid4().hex[:8]}: BREAKING NEWS: Researchers confirm that properly implemented polling mechanism works flawlessly. In a surprising discovery, scientists found that short-polling at regular intervals ensures reliable message delivery even in large channels. Read more at https://www.nytimes.com/2024/06/22/technology/polling-telegram-megachannels.html"

async def send_test_message():
    """Send a test message to the test source channel"""
    
    # Validate environment variables
    if not all([API_ID, API_HASH, TG_PHONE, TEST_SRC_CHANNEL]):
        logger.error("Missing required environment variables. Check your .env file.")
        return False
    
    # Create session directory if needed
    Path(os.path.dirname(TEST_SESSION)).mkdir(parents=True, exist_ok=True)
    
    # Create and start client
    client = TelegramClient(
        TEST_SESSION,
        int(API_ID),
        API_HASH,
        connection=ConnectionTcpAbridged
    )
    
    try:
        # Start client
        await client.start(phone=TG_PHONE)
        
        if not await client.is_user_authorized():
            logger.error("Authorization failed. Check your credentials.")
            return False
        
        logger.info(f"Sending test message to {TEST_SRC_CHANNEL}...")
        
        # Send the test message
        sent_msg = await client.send_message(TEST_SRC_CHANNEL, TEST_MESSAGE)
        
        if sent_msg:
            logger.info(f"Test message sent successfully with ID: {sent_msg.id}")
            logger.info(f"Message: {TEST_MESSAGE[:50]}...")
            logger.info(f"Wait a moment for the bot to detect and process this message via polling")
            return True
        else:
            logger.error("Failed to send test message")
            return False
    
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return False
    finally:
        await client.disconnect()
        logger.info("Disconnected from Telegram")

if __name__ == "__main__":
    # Run the send_test_message function
    if asyncio.run(send_test_message()):
        logger.info("✅ Test message sent successfully")
        logger.info("Now watch your bot's log output to see if it detects and processes this message")
        sys.exit(0)
    else:
        logger.error("❌ Failed to send test message")
        sys.exit(1) 