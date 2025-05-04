#!/usr/bin/env python3
"""
Quick test script to fetch the latest NYT post and translate it to Russian Zoomer slang.
This validates your setup without posting to the destination channel.
"""

import os
import asyncio
import logging
from dotenv import load_dotenv
from telethon import TelegramClient
import openai

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration from environment variables
API_ID = int(os.getenv('TG_API_ID'))
API_HASH = os.getenv('TG_API_HASH')
OPENAI_KEY = os.getenv('OPENAI_API_KEY')
SESSION = os.getenv('TG_SESSION', 'nyt_to_zoom')
SRC_CHANNEL = os.getenv('SRC_CHANNEL')

# Initialize OpenAI client
client = openai.OpenAI(api_key=OPENAI_KEY)

async def translate_text(text):
    """Translate text to Russian Zoomer slang"""
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a Zoomer. Translate the following text into concise, punchy Russian Zoomer slang."
                },
                {"role": "user", "content": text}
            ],
            max_tokens=500,
            temperature=0.8,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"OpenAI API error: {str(e)}")
        raise

async def main():
    """Main test function"""
    logger.info("Starting test run")
    
    # Verify environment variables
    if not all([API_ID, API_HASH, OPENAI_KEY, SRC_CHANNEL]):
        logger.error("Missing required environment variables!")
        return
    
    # Create Telegram client
    async with TelegramClient(SESSION, API_ID, API_HASH) as tg_client:
        logger.info(f"Connected to Telegram, fetching latest post from {SRC_CHANNEL}")
        
        # Get the latest message from source channel
        messages = await tg_client.get_messages(SRC_CHANNEL, limit=1)
        
        if not messages or not messages[0].text:
            logger.error("No messages found or latest message has no text")
            return
            
        latest_msg = messages[0].text
        logger.info(f"Found message: {latest_msg[:100]}...")
        
        # Translate the message
        logger.info("Translating to Russian Zoomer slang...")
        translated = await translate_text(latest_msg)
        
        # Display results
        logger.info("\n----- ORIGINAL TEXT -----\n")
        logger.info(latest_msg)
        logger.info("\n----- TRANSLATED TEXT -----\n")
        logger.info(translated)
        logger.info("\nTest completed successfully!")

if __name__ == "__main__":
    asyncio.run(main()) 