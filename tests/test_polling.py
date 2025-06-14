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
project_root = Path(__file__).resolve().parent.parent # Go up from tests/ to project root
load_dotenv(dotenv_path=project_root / 'app_settings.env', override=True)
load_dotenv(dotenv_path=project_root / '.env', override=False)

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

# Session handling ---------------------------------------------------
# We want polling tests to be fully automated (no interactive code entry)
# and isolated from the main bot session that may be running elsewhere.
# The best practice is:
# 1. Use a **dedicated Telegram account** for tests (recommended) OR
# 2. Store that account's StringSession in an env var so the test can
#    authenticate non-interactively.

# Environment variables checked (highest precedence first):
#   TG_SENDER_COMPRESSED_SESSION_STRING  – base64-gzipped StringSession
#   TG_SENDER_SESSION_STRING             – plain base64 StringSession
#   TG_SESSION                           – fallback path for file-based session
#
# If no session string is provided, we fall back to a file session inside
# the `session/` folder. This may prompt for an auth code the first time,
# so automated CI environments should always set one of the two vars above.

from telethon.sessions import StringSession

# Try dedicated sender session strings first
_compressed_sender_session_b64 = os.getenv("TG_SENDER_COMPRESSED_SESSION_STRING")
_plain_sender_session_b64 = os.getenv("TG_SENDER_SESSION_STRING")

if _compressed_sender_session_b64 or _plain_sender_session_b64:
    # We'll use an in-memory StringSession to avoid generating .session files
    import base64, gzip
    try:
        if _compressed_sender_session_b64:
            _decoded = base64.b64decode(_compressed_sender_session_b64)
            _session_str = gzip.decompress(_decoded).decode()
        else:
            _session_str = base64.b64decode(_plain_sender_session_b64).decode()
        SENDER_SESSION = StringSession(_session_str)
        logger.info("Using StringSession from environment for sender test account")
    except Exception as e:
        logger.error(f"Failed to decode sender StringSession from env vars: {e}")
        # Fallback to file-based session below
        SENDER_SESSION = "session/sender_test_session"  # path without .session
else:
    SENDER_SESSION = "session/sender_test_session"  # path without .session

# Unique prefix for each run (stay below 20 chars to keep test messages short)
MESSAGE_PREFIX = f"POLLING-TEST-{uuid.uuid4().hex[:6]}"

# Define a random test message
TEST_MESSAGE = f"{MESSAGE_PREFIX}: BREAKING NEWS: Researchers confirm that properly implemented polling mechanism works flawlessly. In a surprising discovery, scientists found that short-polling at regular intervals ensures reliable message delivery even in large channels. Read more at https://www.nytimes.com/2024/06/22/technology/polling-telegram-megachannels.html"

async def send_test_message():
    """Send a test message to the test source channel"""
    
    # Validate environment variables
    if not all([API_ID, API_HASH, TG_PHONE, TEST_SRC_CHANNEL]):
        logger.error("Missing required environment variables. Check your .env file.")
        return False
    
    logger.info(f"Using sender session: {SENDER_SESSION}")
    
    # If we're using a file path, ensure directory exists
    if isinstance(SENDER_SESSION, str):
        Path(os.path.dirname(SENDER_SESSION)).mkdir(parents=True, exist_ok=True)

    # Create and start client
    client = None
    try:
        client = TelegramClient(
            SENDER_SESSION,
            int(API_ID),
            API_HASH,
            connection=ConnectionTcpAbridged
        )
        
        # Start client
        logger.info("Connecting and authenticating sender session...")
        await client.start(phone=TG_PHONE) # This will prompt for code if session is new or invalid
        
        if not await client.is_user_authorized():
            logger.error("Authorization failed for sender session. Please run manually to authorize.")
            return False
        logger.info("Sender session authorized.")
        
        logger.info(f"Sending test message to {TEST_SRC_CHANNEL} with prefix {MESSAGE_PREFIX}...")
        
        # Send the test message
        sent_msg = await client.send_message(TEST_SRC_CHANNEL, TEST_MESSAGE)
        
        if sent_msg:
            logger.info(f"Test message sent successfully with ID: {sent_msg.id}")
            logger.info(f"Message: {TEST_MESSAGE[:70]}...")
            logger.info(f"Wait a moment for the bot to detect and process this message via polling")
            return True
        else:
            logger.error("Failed to send test message")
            return False
    
    except Exception as e:
        logger.error(f"Error in send_test_message: {str(e)}", exc_info=True)
        return False
    finally:
        if client and client.is_connected():
            await client.disconnect()
            logger.info("Disconnected from Telegram")

if __name__ == "__main__":
    # Run the send_test_message function
    if asyncio.run(send_test_message()):
        logger.info(f"✅ Test message ({MESSAGE_PREFIX}) sent successfully using {SENDER_SESSION}")
        logger.info("Now watch your bot's log output to see if it detects and processes this message")
        # Pass the unique message prefix to stdout for the calling script to capture
        print(f"MESSAGE_PREFIX_SENT:{MESSAGE_PREFIX}")
        sys.exit(0)
    else:
        logger.error("❌ Failed to send test message")
        sys.exit(1) 