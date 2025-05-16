#!/usr/bin/env python3
"""
Simple Telegram authentication script to generate a valid session file
"""

import os
import asyncio
import logging
from telethon import TelegramClient
from telethon.network import ConnectionTcpAbridged
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('telegram_auth')

# Load environment variables
load_dotenv()

# Get configuration
API_ID = int(os.getenv('TG_API_ID'))
API_HASH = os.getenv('TG_API_HASH')
PHONE = os.getenv('TG_PHONE')
SESSION_PATH = 'session/test_session_persistent'

async def main():
    """Create a session file for Telegram"""
    logger.info(f"Starting Telegram authentication for session: {SESSION_PATH}")
    
    # Create the directory if it doesn't exist
    os.makedirs(os.path.dirname(SESSION_PATH), exist_ok=True)
    
    # Create the client
    client = TelegramClient(
        SESSION_PATH, 
        API_ID, 
        API_HASH,
        connection=ConnectionTcpAbridged,
        use_ipv6=False,
        auto_reconnect=True
    )
    
    try:
        logger.info("Connecting to Telegram...")
        await client.connect()
        
        # Check if already authenticated
        if await client.is_user_authorized():
            logger.info("Already authenticated!")
            me = await client.get_me()
            logger.info(f"Logged in as: {me.first_name} (ID: {me.id})")
        else:
            # Start authentication process
            logger.info("Not authenticated. Starting authentication process...")
            
            if not PHONE:
                phone = input("Please enter your phone number (with country code): ")
            else:
                phone = PHONE
                
            logger.info(f"Sending code to {phone}")
            await client.send_code_request(phone)
            
            code = input("Enter the code you received: ")
            
            try:
                await client.sign_in(phone, code)
                logger.info("Successfully authenticated!")
                
                me = await client.get_me()
                logger.info(f"Logged in as: {me.first_name} (ID: {me.id})")
            except Exception as e:
                logger.error(f"Error during authentication: {e}")
                
                # Check if two-factor auth is enabled
                if "2FA" in str(e) or "password" in str(e).lower():
                    password = input("Enter your two-factor authentication password: ")
                    await client.sign_in(password=password)
                    logger.info("Successfully authenticated with 2FA!")
                    
                    me = await client.get_me()
                    logger.info(f"Logged in as: {me.first_name} (ID: {me.id})")
        
        # Verify session is working
        logger.info("Testing connection...")
        dialogs = await client.get_dialogs(limit=1)
        logger.info(f"Connected successfully! Found {len(dialogs)} dialogs.")
        
        logger.info(f"Session file created at: {SESSION_PATH}.session")
        logger.info("You can now run the bot with this session.")
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
    finally:
        await client.disconnect()
        logger.info("Disconnected")

if __name__ == "__main__":
    asyncio.run(main()) 