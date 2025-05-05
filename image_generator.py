"""
Image generation functionality for the Telegram Zoomer Bot
"""

import logging
import os
import aiohttp
import asyncio
from io import BytesIO

logger = logging.getLogger(__name__)

async def generate_image_for_post(client, text, max_length=100):
    """
    Generate an image related to the post content using OpenAI's DALL-E model
    
    Args:
        client: OpenAI client instance
        text: Text of the post to generate an image for
        max_length: Maximum length of text to use for image prompt
    
    Returns:
        BytesIO object containing the image or None if generation failed
    """
    try:
        # Create a prompt based on the post text
        # Truncate post text to prevent overly long prompts
        short_text = text[:max_length] + "..." if len(text) > max_length else text
        
        # Create a descriptive prompt for DALL-E based on the content
        prompt = f"Create a photorealistic, journalistic image visualizing this news: {short_text}"
        
        logger.info(f"Generating image with prompt: {prompt[:100]}...")
        
        # Generate the image using DALL-E
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        
        # Get the image URL
        image_url = response.data[0].url
        logger.info(f"Image generated successfully: {image_url[:100]}...")
        
        # Download the image
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status == 200:
                    image_data = await resp.read()
                    return BytesIO(image_data)
                else:
                    logger.error(f"Failed to download image: {resp.status}")
                    return None
                    
    except Exception as e:
        logger.error(f"Error generating image: {str(e)}")
        return None

async def process_multiple_posts(client, channel, limit=10):
    """
    Process multiple most recent posts from a channel
    
    Args:
        client: Telegram client instance
        channel: Source channel ID or username
        limit: Number of most recent posts to process
    
    Returns:
        List of message objects retrieved
    """
    try:
        messages = []
        async for message in client.iter_messages(channel, limit=limit):
            if message.text:  # Only include messages with text
                messages.append(message)
                
        logger.info(f"Retrieved {len(messages)} messages from channel {channel}")
        return messages
    except Exception as e:
        logger.error(f"Error retrieving messages: {str(e)}")
        return [] 