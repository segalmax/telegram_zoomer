"""
Image generation functionality for the Telegram Zoomer Bot
"""

import logging
import os
import aiohttp
import asyncio
import ssl
import certifi
import time
from io import BytesIO
import platform

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
        start_time = time.time()
        logger.info(f"Starting image generation for text: {text[:30]}...")
        
        # Create a prompt based on the post text
        # Truncate post text to prevent overly long prompts
        short_text = text[:max_length] + "..." if len(text) > max_length else text
        
        # Create a descriptive prompt for DALL-E based on the content
        prompt = f"Create a photorealistic, journalistic image visualizing this news: {short_text}"
        
        logger.info(f"Generated prompt: {prompt[:100]}...")
        
        # Generate the image using DALL-E
        logger.info("Sending request to OpenAI DALL-E API...")
        api_start_time = time.time()
        try:
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1,
            )
            api_duration = time.time() - api_start_time
            logger.info(f"OpenAI API request completed in {api_duration:.2f} seconds")
        except Exception as api_error:
            logger.error(f"OpenAI API error: {str(api_error)}", exc_info=True)
            return None
        
        # Get the image URL
        image_url = response.data[0].url
        logger.info(f"Image URL received: {image_url[:100]}...")
        
        # Create SSL context with proper certificates for macOS
        ssl_context = None
        if platform.system() == 'Darwin':  # macOS
            logger.info("Using macOS SSL context with certifi for image download")
            ssl_context = ssl.create_default_context(cafile=certifi.where())
        
        # Download the image
        logger.info("Starting image download...")
        download_start_time = time.time()
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            try:
                logger.info(f"Sending HTTP GET to URL: {image_url[:50]}...")
                async with session.get(image_url, timeout=60) as resp:
                    status = resp.status
                    logger.info(f"Download response status: {status}")
                    
                    if status == 200:
                        logger.info("Reading image data...")
                        image_data = await resp.read()
                        image_size = len(image_data)
                        download_duration = time.time() - download_start_time
                        logger.info(f"Image downloaded successfully: {image_size} bytes in {download_duration:.2f} seconds")
                        
                        total_duration = time.time() - start_time
                        logger.info(f"Total image generation process completed in {total_duration:.2f} seconds")
                        return BytesIO(image_data)
                    else:
                        logger.error(f"Failed to download image: HTTP {status}")
                        logger.error(f"Response headers: {resp.headers}")
                        return None
            except asyncio.TimeoutError:
                logger.error("Timeout occurred while downloading the image")
                logger.info("Returning URL instead of image data due to download timeout")
                return image_url
            except Exception as download_err:
                logger.error(f"Download error: {str(download_err)}", exc_info=True)
                logger.info("Returning URL instead of image data due to download error")
                # If we can't download the image, return the URL instead
                return image_url
                    
    except Exception as e:
        logger.error(f"Error in generate_image_for_post: {str(e)}", exc_info=True)
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
        start_time = time.time()
        logger.info(f"Fetching up to {limit} messages from channel: {channel}")
        
        messages = []
        count = 0
        async for message in client.iter_messages(channel, limit=limit):
            count += 1
            if message.text:  # Only include messages with text
                messages.append(message)
                logger.info(f"Found message {count} with ID {message.id}: {message.text[:50]}...")
            else:
                logger.info(f"Skipping message {count} with ID {message.id} (no text content)")
                
        duration = time.time() - start_time
        logger.info(f"Retrieved {len(messages)} messages with text out of {count} total in {duration:.2f} seconds")
        return messages
    except Exception as e:
        logger.error(f"Error in process_multiple_posts: {str(e)}", exc_info=True)
        return [] 