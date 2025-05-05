#!/usr/bin/env python3
"""
Core functionality test for Telegram Zoomer Bot

This test verifies that the OpenAI integration for translations and image generation works correctly.
"""

import os
import asyncio
import logging
from dotenv import load_dotenv
import openai
from translator import get_openai_client, translate_text
from image_generator import generate_image_for_post

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration - using test channels instead of production ones
OPENAI_KEY = os.getenv('OPENAI_API_KEY')

# Test data
TEST_MESSAGE = (
    "BREAKING NEWS: Scientists discover new species of deep-sea creatures "
    "near hydrothermal vents in the Pacific Ocean. The previously unknown "
    "organisms display remarkable adaptation to extreme pressure and "
    "temperature conditions, potentially offering insights into the "
    "evolution of life on Earth and beyond."
)

async def test_translations():
    """Test translation functionality"""
    if not OPENAI_KEY:
        logger.error("Missing OpenAI API key")
        return False
        
    # Initialize OpenAI client
    logger.info("Initializing OpenAI client")
    client = get_openai_client(OPENAI_KEY)
    
    try:
        # Test LEFT style translation
        logger.info("Testing LEFT style translation...")
        left = await translate_text(client, TEST_MESSAGE, 'left')
        if left:
            logger.info(f"LEFT translation successful: {left[:100]}...")
        else:
            logger.error("LEFT translation failed")
            return False
            
        # Test RIGHT style translation    
        logger.info("Testing RIGHT style translation...")
        right = await translate_text(client, TEST_MESSAGE, 'right')
        if right:
            logger.info(f"RIGHT translation successful: {right[:100]}...")
        else:
            logger.error("RIGHT translation failed")
            return False
        
        # Test image generation (optional)
        logger.info("Testing image generation...")
        image_result = await generate_image_for_post(client, TEST_MESSAGE)
        if image_result:
            logger.info("Image generation successful")
        else:
            logger.warning("Image generation failed")
            # Not a critical failure
        
        logger.info("All core tests passed!")
        return True
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_translations())
    if success:
        logger.info("✅ Core functionality test successful")
        exit(0)
    else:
        logger.error("❌ Core functionality test failed")
        exit(1) 