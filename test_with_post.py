#!/usr/bin/env python3
"""
Test script that fetches the latest post from source channel,
translates it into two styles (left-leaning zoomer and right-wing bidlo), and posts both.
"""

import os
import asyncio
import logging
from dotenv import load_dotenv
from telethon import TelegramClient
import openai
from translator import get_openai_client, translate_text

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
DST_CHANNEL = os.getenv('DST_CHANNEL')

# Initialize OpenAI client
client = get_openai_client(OPENAI_KEY)

async def main():
    """Main test function"""
    logger.info("Starting dual-style test run")
    if not all([API_ID, API_HASH, OPENAI_KEY, SRC_CHANNEL, DST_CHANNEL]):
        logger.error("Missing required environment variables!")
        return

    async with TelegramClient(SESSION, API_ID, API_HASH) as tg_client:
        logger.info(f"Fetching latest post from {SRC_CHANNEL}")
        msgs = await tg_client.get_messages(SRC_CHANNEL, limit=1)
        if not msgs or not msgs[0].text:
            logger.error("No valid message found")
            return
        text = msgs[0].text

        # Left-leaning translation
        logger.info("Translating LEFT style...")
        left = await translate_text(client, text, 'left')
        logger.info(f"LEFT translation snippet: {left[:100]}...")
        # Post heading then the translation
        await tg_client.send_message(DST_CHANNEL, "🟢 LEFT-ZOOMER VERSION:")
        await tg_client.send_message(DST_CHANNEL, left)
        logger.info("Posted left-leaning version and translation")

        # Right-wing translation
        logger.info("Translating RIGHT style...")
        right = await translate_text(client, text, 'right')
        logger.info(f"RIGHT translation snippet: {right[:100]}...")
        # Post heading then the translation
        await tg_client.send_message(DST_CHANNEL, "🔴 RIGHT-BIDLO VERSION:")
        await tg_client.send_message(DST_CHANNEL, right)
        logger.info("Posted right-wing version and translation")

        logger.info("Dual test run complete!")

if __name__ == "__main__":
    asyncio.run(main()) 