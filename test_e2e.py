#!/usr/bin/env python3
"""
End-to-end test script for Telegram Zoomer Bot with image generation

This script tests the flow from a test source channel to a destination channel
with image generation and translation.
"""

import os
import asyncio
import logging
from dotenv import load_dotenv
from telethon import TelegramClient, events
import openai
from translator import get_openai_client, translate_text
from image_generator import generate_image_for_post

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration - using test channels instead of production ones
API_ID = int(os.getenv('TG_API_ID'))
API_HASH = os.getenv('TG_API_HASH')
OPENAI_KEY = os.getenv('OPENAI_API_KEY')
SESSION = os.getenv('TG_SESSION', 'nyt_to_zoom')
TEST_SRC_CHANNEL = os.getenv('TEST_SRC_CHANNEL', 'nyttest')         # Test source channel
TEST_DST_CHANNEL = os.getenv('TEST_DST_CHANNEL', 'nytzoomerutest')  # Test destination channel

# Initialize OpenAI client
client = get_openai_client(OPENAI_KEY)

async def post_test_message(tg_client):
    """Post a test message to the test source channel"""
    test_message = (
        "BREAKING NEWS: Scientists discover new species of deep-sea creatures "
        "near hydrothermal vents in the Pacific Ocean. The previously unknown "
        "organisms display remarkable adaptation to extreme pressure and "
        "temperature conditions, potentially offering insights into the "
        "evolution of life on Earth and beyond."
    )
    
    try:
        logger.info(f"Posting test message to {TEST_SRC_CHANNEL}")
        await tg_client.send_message(TEST_SRC_CHANNEL, test_message)
        logger.info("Test message posted successfully")
        return True
    except Exception as e:
        logger.error(f"Error posting test message: {str(e)}")
        return False

async def translate_and_post_with_image(tg_client, text):
    """Translate text and post to destination channel with image"""
    try:
        # Generate image based on post content
        logger.info("Generating image for post...")
        result = await generate_image_for_post(client, text)
        
        image_data = None
        image_url = None
        
        if result:
            if isinstance(result, str):
                # It's a URL
                image_url = result
                logger.info(f"Using image URL: {image_url[:100]}...")
            else:
                # It's BytesIO data
                image_data = result
                logger.info("Image data received successfully")
        else:
            logger.error("Failed to generate image")
            
        # Translate in both styles
        logger.info("Translating in LEFT style...")
        left = await translate_text(client, text, 'left')
        logger.info(f"LEFT translation snippet: {left[:100]}...")
        
        # Post header, image, and translation
        await tg_client.send_message(TEST_DST_CHANNEL, "🟢 LEFT-ZOOMER TEST VERSION:")
        
        if image_data:
            # Post with image data
            await tg_client.send_file(TEST_DST_CHANNEL, image_data, caption=left[:1024])
            logger.info("Posted left-leaning version with image data")
        elif image_url:
            # Post with image URL
            left_with_url = f"{left}\n\n🖼️ {image_url}"
            await tg_client.send_message(TEST_DST_CHANNEL, left_with_url)
            logger.info("Posted left-leaning version with image URL")
        else:
            # Post text only
            await tg_client.send_message(TEST_DST_CHANNEL, left)
            logger.info("Posted left-leaning version (text only)")
        
        logger.info("Translating in RIGHT style...")
        right = await translate_text(client, text, 'right')
        logger.info(f"RIGHT translation snippet: {right[:100]}...")
        
        # Post right-wing version
        await tg_client.send_message(TEST_DST_CHANNEL, "🔴 RIGHT-BIDLO TEST VERSION:")
        await tg_client.send_message(TEST_DST_CHANNEL, right)
        logger.info("Posted right-wing version")
        
        return True
    except Exception as e:
        logger.error(f"Error in translate_and_post: {str(e)}")
        return False

async def main():
    """Main test function"""
    logger.info("Starting end-to-end test")
    
    # Verify required environment variables
    if not all([API_ID, API_HASH, OPENAI_KEY, TEST_SRC_CHANNEL, TEST_DST_CHANNEL]):
        logger.error("Missing required environment variables")
        return
    
    # Create client
    tg_client = TelegramClient(SESSION, API_ID, API_HASH)
    
    try:
        await tg_client.start()
        logger.info("Telegram client started")
        
        # Post a test message to source channel
        if await post_test_message(tg_client):
            # Wait a moment to ensure message is processed
            await asyncio.sleep(2)
            
            # Get the most recent message from test source channel
            async for message in tg_client.iter_messages(TEST_SRC_CHANNEL, limit=1):
                if message and message.text:
                    logger.info(f"Processing test message: {message.text[:50]}...")
                    await translate_and_post_with_image(tg_client, message.text)
                    break
            
        logger.info("End-to-end test completed")
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
    finally:
        await tg_client.disconnect()

if __name__ == "__main__":
    asyncio.run(main()) 