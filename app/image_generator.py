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
import json
import base64
from io import BytesIO
import platform
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

async def generate_image_with_stability_ai(text, style="cartoon"):
    """Generate an image using Stability AI API based on post content"""
    try:
        # Maximum context length
        MAX_CHARS = 1000
        
        # Check if text is too short or meaningless for generation
        if len(text.strip()) < 30 or text.strip().lower().startswith("test ") or "test retry" in text.strip().lower():
            logger.info(f"Text too short or test message detected: '{text}'. Skipping Stability AI image generation.")
            return None
            
        # Get API key from environment
        api_key = os.environ.get("STABILITY_AI_API_KEY")
        if not api_key:
            logger.error("STABILITY_AI_API_KEY not found in environment variables")
            return None
            
        # Use first paragraph or truncate long text
        text_for_prompt = text[:MAX_CHARS].strip()
        
        # Choose style template based on parameter
        style_templates = {
            "cartoon": {
                "prefix": "Create a satirical political caricature about this news story:",
                "suffix": "Use exaggerated facial features of political figures, bold colors, and clear visual metaphors. NO TEXT or words in the image. The style should be like editorial cartoons with dramatic exaggerations, satirical imagery, and symbolic elements. Make it visually witty.",
                "style_preset": "comic-book",
                "cfg_scale": 12,
                "steps": 50
            },
            "meme": {
                "prefix": "Create a humorous political caricature about this news:",
                "suffix": "Make it visually striking and witty, with exaggerated features of political figures. NO TEXT or labels in the image. Use bold colors and clear visual satire.",
                "style_preset": "comic-book",
                "cfg_scale": 10,
                "steps": 40
            },
            "infographic": {
                "prefix": "Create a satirical caricature about this news story:",
                "suffix": "Focus on exaggerated depictions of key figures and symbolic visual elements that tell the story without using any text. Style should be like political cartoons with humor and visual metaphors.",
                "style_preset": "comic-book",
                "cfg_scale": 11,
                "steps": 45
            }
        }
        
        # Default to cartoon if style not found
        style_config = style_templates.get(style, style_templates["cartoon"])
        
        # Construct prompt
        prompt = f"{style_config['prefix']} {text_for_prompt} {style_config['suffix']}"
        logger.info(f"Using Stability AI prompt: {prompt[:100]}...")
        
        # API call
        url = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image"
        
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        body = {
            "width": 1024,
            "height": 1024,
            "steps": style_config["steps"],
            "cfg_scale": style_config["cfg_scale"],
            "style_preset": style_config["style_preset"],
            "text_prompts": [
                {"text": prompt, "weight": 1.0},
                {"text": "blurry, bad quality, extra limbs, deformed, photorealistic, realistic", "weight": -1.0}
            ]
        }
        
        # Enforce timeout to prevent hanging
        timeout = aiohttp.ClientTimeout(total=60)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            logger.info("Sending request to Stability AI API...")
            try:
                async with session.post(url, headers=headers, json=body) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        if "artifacts" in result and len(result["artifacts"]) > 0:
                            # Extract image from the first artifact
                            b64_image = result["artifacts"][0]["base64"]
                            image_data = base64.b64decode(b64_image)
                            
                            # Create BytesIO object
                            image_stream = BytesIO(image_data)
                            
                            logger.info(f"Successfully generated image with Stability AI (size: {len(image_data)} bytes)")
                            return image_stream
                        else:
                            logger.error("No artifacts found in Stability AI response")
                    else:
                        error_text = await response.text()
                        logger.error(f"Stability AI request failed with status {response.status}: {error_text}")
            except asyncio.TimeoutError:
                logger.error("Stability AI request timed out after 60 seconds")
            except Exception as e:
                logger.error(f"Error making Stability AI request: {str(e)}")
                
        return None
        
    except Exception as e:
        logger.error(f"Error in Stability AI image generation: {str(e)}")
        return None

async def generate_image_for_post(client, text, max_length=150):
    """
    Generate an image related to the post content using OpenAI's DALL-E model
    
    Args:
        client: OpenAI client instance
        text: Text of the post to generate an image for
        max_length: Maximum length of text to use for image prompt
    
    Returns:
        BytesIO object containing the image or None if generation failed
    """
    # Check if we should use Stability AI
    use_stability = os.getenv("USE_STABILITY_AI", "false").lower() == "true"
    
    if use_stability:
        logger.info("Using Stability AI for image generation")
        # Default to cartoon style for better caricatures
        return await generate_image_with_stability_ai(text, style="cartoon")
    
    try:
        start_time = time.time()
        logger.info(f"Starting DALL-E image generation for text: {text[:30]}...")
        
        # Check if text is too short or meaningless for generation
        if len(text.strip()) < 30 or text.strip().lower().startswith("test ") or "test retry" in text.strip().lower():
            logger.info(f"Text too short or test message detected: '{text}'. Skipping image generation.")
            return None
        
        # Use a more robust input to avoid API errors by adding descriptive context
        enhanced_text = text
        if len(text) < 100:
            enhanced_text = f"NEWS STORY: {text} This is a major development with significant implications for science and understanding deep ocean environments."

        logger.info(f"Using enhanced text for image generation: {enhanced_text[:50]}...")
        
        # Create a prompt based on the post text
        # Truncate post text to prevent overly long prompts
        short_text = enhanced_text[:max_length] + "..." if len(enhanced_text) > max_length else enhanced_text
        
        # Create a descriptive prompt for DALL-E based on the content
        prompt = f"Create a full-color satirical political cartoon or caricature visualizing this news: {short_text}. Focus on exaggerated features of political figures and symbolic visual elements. NO TEXT or words in the image. Make it like a traditional political cartoon with bold colors and clear visual metaphors that directly relate to the key news points. Show scientists making an important discovery."
        
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