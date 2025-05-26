#!/usr/bin/env python3
"""
Telegram Zoomer Bot - Translates posts into zoomer slang
"""

import os
import asyncio
import logging
import time
import sys
import uuid
import re
from pathlib import Path
from telethon import TelegramClient, events
from telethon.network import ConnectionTcpFull, ConnectionTcpAbridged, ConnectionTcpIntermediate
from telethon.sessions import StringSession
from telethon import utils
import anthropic
from dotenv import load_dotenv
from .translator import get_anthropic_client, translate_text
from .image_generator import generate_image_for_post
from .session_manager import setup_session, load_app_state, save_app_state
from telethon.tl.functions.account import UpdateStatusRequest
from telethon.tl.functions.updates import GetChannelDifferenceRequest
from telethon.tl.types import InputChannel, ChannelMessagesFilterEmpty
from telethon.errors import SessionPasswordNeededError
from datetime import datetime, timedelta
import random
import argparse
from .pts_manager import get_pts, update_pts

# Load environment variables explicitly from project root.
# Order of loading determines precedence for non-secret variables if keys overlap.
# 1. app_settings.env: for non-secret app configurations. These will override OS env vars if present.
# 2. .env: for secrets. These will NOT override anything already set by OS or app_settings.env.

project_root = Path(__file__).resolve().parent.parent

# Load non-secret app settings (e.g., channel names, feature flags)
# These will take precedence over OS environment variables for the same keys.
load_dotenv(dotenv_path=project_root / 'app_settings.env', override=True)

# Load secrets from .env file.
# These will only be loaded if not already present in the environment (e.g., from OS or app_settings.env).
load_dotenv(dotenv_path=project_root / '.env', override=False)

# Get configuration from environment variables
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
PHONE = os.getenv('PHONE') or os.getenv('TG_PHONE')  # Check both variable names

# Check if running on Heroku
IS_HEROKU = os.getenv('DYNO') is not None

SRC_CHANNEL = os.getenv('SRC_CHANNEL')
DST_CHANNEL = os.getenv('DST_CHANNEL')
TRANSLATION_STYLE = os.getenv('TRANSLATION_STYLE', 'right')  # right only by default
GENERATE_IMAGES = os.getenv('GENERATE_IMAGES', 'true').lower() == 'true'
ANTHROPIC_KEY = os.getenv('ANTHROPIC_API_KEY')
PROCESS_RECENT = os.getenv('PROCESS_RECENT', 0)
CHECK_CHANNEL_INTERVAL = int(os.getenv('CHECK_CHANNEL_INTERVAL', '300'))  # Default to 5 minutes
KEEP_ALIVE_INTERVAL = int(os.getenv('KEEP_ALIVE_INTERVAL', '60'))  # Keep connection alive every minute
MANUAL_POLL_INTERVAL = int(os.getenv('MANUAL_POLL_INTERVAL', '180'))  # Manual polling every 3 minutes
USE_STABILITY_AI = os.getenv('USE_STABILITY_AI', 'false').lower() == 'true'

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger('app.bot')

# Use different session paths for Heroku vs local development
if IS_HEROKU:
    SESSION_PATH = os.getenv('TG_SESSION', 'session/heroku_bot_session')
    logger.info(f"Running on Heroku, using session path: {SESSION_PATH}")
else:
    SESSION_PATH = os.getenv('TG_SESSION', 'session/local_bot_session')
    logger.info(f"Running locally, using session path: {SESSION_PATH}")

# Check for TEST_SRC_CHANNEL and TEST_DST_CHANNEL environment variables
# This helps us switch to test mode when running tests
TEST_MODE = False
if os.getenv('TEST_MODE', 'false').lower() == 'true':
    TEST_MODE = True
    logger.info("Running in TEST MODE")
    # Use test channels if they are defined
    if os.getenv('TEST_SRC_CHANNEL'):
        SRC_CHANNEL = os.getenv('TEST_SRC_CHANNEL')
        logger.info(f"Using TEST source channel: {SRC_CHANNEL}")
    if os.getenv('TEST_DST_CHANNEL'):
        DST_CHANNEL = os.getenv('TEST_DST_CHANNEL')
        logger.info(f"Using TEST destination channel: {DST_CHANNEL}")

# Configuration from environment variables
try:
    API_ID = int(os.getenv('TG_API_ID'))
    API_HASH = os.getenv('TG_API_HASH')
    ANTHROPIC_KEY = os.getenv('ANTHROPIC_API_KEY')
except (TypeError, ValueError) as e:
    logger.error(f"Error: TG_API_ID, TG_API_HASH, or ANTHROPIC_API_KEY is not set correctly in .env: {e}")
    sys.exit("Critical environment variables missing or invalid. Exiting.")

TG_PHONE = os.getenv('TG_PHONE') # Optional, bot will prompt

# Use session manager to handle session persistence
SESSION = setup_session()

if not SRC_CHANNEL or not DST_CHANNEL:
    logger.error("Error: SRC_CHANNEL or DST_CHANNEL is not set in .env.")
    sys.exit("Source/Destination channel environment variables missing. Exiting.")

# Initialize Anthropic client
anthropic_client = None
if ANTHROPIC_KEY:
    anthropic_client = get_anthropic_client(ANTHROPIC_KEY)
else:
    logger.error("ANTHROPIC_API_KEY not found. Translation functions will fail.")
    # Decide if this is fatal or if bot can run without Anthropic (e.g. only relaying)

async def translate_and_post(client_instance, txt, message_id=None, destination_channel=None, message_entity_urls=None):
    # Renamed client to client_instance to avoid conflict with openai_client module
    try:
        start_time = time.time()
        logger.info(f"Starting translation and posting for message ID: {message_id}")
        
        dst_channel_to_use = destination_channel or DST_CHANNEL
        logger.info(f"Using destination channel: {dst_channel_to_use}")
        
        image_data = None
        image_url_str = None  # Renamed from image_url to avoid confusion
        
        # Re-evaluate GENERATE_IMAGES at runtime so that tests
        # can control it via environment variables _after_ this module
        # has already been imported.
        generate_images = os.getenv("GENERATE_IMAGES", "true").lower() == "true"

        # Note: Image generation still requires OpenAI, so we'll skip it for now with Claude
        # TODO: Implement image generation with Claude or keep separate OpenAI client for images
        if generate_images:
            logger.warning("Image generation temporarily disabled during Claude translation upgrade")

        # Get the original message link format: https://t.me/c/CHANNEL_ID/MESSAGE_ID
        # or for public channels: https://t.me/CHANNEL_NAME/MESSAGE_ID
        message_link = f"https://t.me/{SRC_CHANNEL.replace('@', '')}/{message_id}" if message_id else "Unknown source"
        logger.info(f"Original message link: {message_link}")

        # Include both the original message link and any extracted URLs from message entities
        # Format as hyperlinks to hide the full URLs
        source_footer = f"\n\n🔗 [Оригинал]({message_link})"
        
        # Add extracted links from message entities if available
        if message_entity_urls and len(message_entity_urls) > 0:
            source_footer += f"\n🔗 [Ссылка из статьи]({message_entity_urls[0]})"
            logger.info(f"Including extracted URL from message: {message_entity_urls[0]}")
        
        async def send_message_parts(channel, text_content, image_file=None, image_url_link=None):
            if image_file:
                # Use up to 1024 characters for caption
                caption = text_content[:1024]
                await client_instance.send_file(channel, image_file, caption=caption, parse_mode='md')
                # If text is too long for caption, send the rest as a separate message
                if len(text_content) > 1024:
                    remaining_text = text_content[1024:]
                    if remaining_text.strip(): # ensure remaining_text actually has content
                        await client_instance.send_message(channel, remaining_text, parse_mode='md')
            elif image_url_link:
                full_message = f"{text_content}\\n\\n🖼️ {image_url_link}"
                await client_instance.send_message(channel, full_message, parse_mode='md')
            else:
                await client_instance.send_message(channel, text_content, parse_mode='md')

        # Get translation style from environment (default to 'both')
        translation_style = os.getenv("TRANSLATION_STYLE", "right").lower()

        # Check for Anthropic client *before* attempting to translate
        if not anthropic_client:
            logger.error("Cannot translate without Anthropic client.")
            return False
        
        # Append links information and article content to the original text for context
        translation_context = txt
        if message_entity_urls and len(message_entity_urls) > 0:
            # Try to extract article content from the first URL
            from .article_extractor import extract_article
            article_text = extract_article(message_entity_urls[0])
            
            if article_text:
                # Include article content for better translation context
                translation_context += f"\n\nArticle content from {message_entity_urls[0]}:\n{article_text}"
                logger.info(f"Added article content ({len(article_text)} chars) to translation context")
            else:
                # Fallback to just mentioning the link
                translation_context += f"\n\nNote: This message contains a link: {message_entity_urls[0]}"
                logger.info("Article extraction failed, using fallback link mention")
        
        if translation_style == 'right' or translation_style == 'both':
            logger.info("Translating in RIGHT-BIDLO style...")
            translated_text = await translate_text(anthropic_client, translation_context, 'right')
            
            # Clean content without header for better presentation
            right_content = f"{translated_text}{source_footer}"
            await send_message_parts(dst_channel_to_use, right_content, image_data, image_url_str)
            logger.info(f"Posted right-bidlo version")
        
        if translation_style == 'left' or translation_style == 'both':
            logger.info("Translating in LEFT-ZOOMER style...")
            translated_text = await translate_text(anthropic_client, translation_context, 'left')
            
            # Combine header with translated content
            left_content = f"🔵 LEFT-ZOOMER VERSION:\n\n{translated_text}{source_footer}"
            await send_message_parts(dst_channel_to_use, left_content, None, None)
            logger.info(f"Posted left-zoomer version")
        
        logger.info(f"Total processing time for message: {time.time() - start_time:.2f} seconds")
        return True
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}", exc_info=True)
        return False

async def setup_event_handlers(client_instance):
    # Renamed client to client_instance
    @client_instance.on(events.NewMessage(chats=SRC_CHANNEL))
    async def handle_new_message(event):
        try:
            txt = event.message.message
            if not txt: return
            logger.info(f"Processing new message ID {event.message.id}: {txt[:50]}...")
            
            # Extract URLs from message entities
            message_entity_urls = []
            if hasattr(event.message, 'entities') and event.message.entities:
                for entity in event.message.entities:
                    if hasattr(entity, 'url') and entity.url:
                        # Entity already has URL property
                        message_entity_urls.append(entity.url)
                        logger.info(f"Found URL entity with direct URL: {entity.url}")
                    elif hasattr(entity, '_') and entity._ == 'MessageEntityTextUrl':
                        # TextUrl entity type
                        if hasattr(entity, 'url'):
                            message_entity_urls.append(entity.url)
                            logger.info(f"Found TextUrl entity: {entity.url}")
                    elif hasattr(entity, '_') and entity._ in ('MessageEntityUrl', 'MessageEntityTextUrl'):
                        # Extract URL from the message text using offset and length
                        if hasattr(entity, 'offset') and hasattr(entity, 'length'):
                            url_text = txt[entity.offset:entity.offset + entity.length]
                            if url_text.startswith('http'):
                                message_entity_urls.append(url_text)
                                logger.info(f"Extracted URL from text: {url_text}")
                            else:
                                logger.info(f"Found URL-like entity but not a valid URL: {url_text}")
            
            logger.info(f"Extracted URLs from message: {message_entity_urls}")
            
            success = await translate_and_post(client_instance, txt, event.message.id, message_entity_urls=message_entity_urls)
            if success:
                current_state = load_app_state()
                current_state['message_id'] = event.message.id
                current_state['timestamp'] = event.message.date.isoformat() # Ensure ISO format
                # PTS is not directly available here, rely on GetChannelDifference for PTS updates
                # If this handler is primary, might need a way to estimate or fetch PTS if critical
                save_app_state(current_state)
                logger.info(f"App state updated after processing new message ID {event.message.id}")
        except Exception as e:
            logger.error(f"Error in handle_new_message: {str(e)}", exc_info=True)

async def process_recent_posts(client_instance, limit=10, timeout=300):
    # Renamed client to client_instance
    try:
        logger.info(f"Begin processing {limit} most recent posts from channel '{SRC_CHANNEL}'")
        start_time = time.time()
        fetch_timeout = min(60, timeout / 2)
        try:
            messages = await asyncio.wait_for(
                client_instance.get_messages(SRC_CHANNEL, limit=limit), 
                timeout=fetch_timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"Timed out fetching messages from '{SRC_CHANNEL}'")
            return 0
        
        if not messages: logger.warning(f"No messages found in '{SRC_CHANNEL}'"); return 0
        
        processed_count = 0
        for msg in reversed(messages):
            if not msg.text: continue
            if time.time() - start_time > timeout - 30: # Reserve 30s
                logger.warning("Approaching timeout, stopping batch processing.")
                break
            logger.info(f"Processing message {msg.id}: {msg.text[:50]}...")
            
            # Extract URLs from message entities
            message_entity_urls = []
            if hasattr(msg, 'entities') and msg.entities:
                for entity in msg.entities:
                    if hasattr(entity, 'url') and entity.url:
                        # Entity already has URL property
                        message_entity_urls.append(entity.url)
                        logger.info(f"Found URL entity with direct URL: {entity.url}")
                    elif hasattr(entity, '_') and entity._ == 'MessageEntityTextUrl':
                        # TextUrl entity type
                        if hasattr(entity, 'url'):
                            message_entity_urls.append(entity.url)
                            logger.info(f"Found TextUrl entity: {entity.url}")
                    elif hasattr(entity, '_') and entity._ in ('MessageEntityUrl', 'MessageEntityTextUrl'):
                        # Extract URL from the message text using offset and length
                        if hasattr(entity, 'offset') and hasattr(entity, 'length'):
                            url_text = msg.text[entity.offset:entity.offset + entity.length]
                            if url_text.startswith('http'):
                                message_entity_urls.append(url_text)
                                logger.info(f"Extracted URL from text: {url_text}")
                            else:
                                logger.info(f"Found URL-like entity but not a valid URL: {url_text}")
            
            logger.info(f"Extracted URLs from message: {message_entity_urls}")
            
            processing_msg_timeout = min(180, (timeout - (time.time() - start_time)) / (len(messages) - processed_count + 1))
            try:
                success = await asyncio.wait_for(
                    translate_and_post(client_instance, msg.text, msg.id, message_entity_urls=message_entity_urls),
                    timeout=processing_msg_timeout
                )
                if success: processed_count += 1
            except asyncio.TimeoutError:
                logger.error(f"Timed out processing message {msg.id}")
            except Exception as e:
                logger.error(f"Error processing message {msg.id}: {str(e)}", exc_info=True)
            await asyncio.sleep(1) # Rate limit
        logger.info(f"Batch processing completed. Processed {processed_count}/{len(messages)} messages")
        return processed_count
    except Exception as e:
        logger.error(f"Error in batch processing: {str(e)}", exc_info=True)
        return 0

async def ping_server(client_instance):
    # Renamed client to client_instance
    logger.info("Starting background ping process...")
    while True:
        try:
            if not client_instance.is_connected():
                logger.warning("Connection lost, attempting to reconnect...")
                await client_instance.connect()
            if await client_instance.is_user_authorized(): # Check authorization before get_me
                me = await client_instance.get_me()
                if me: logger.info(f"Ping successful - connected as {me.first_name}")
                else: logger.warning("Ping failed - no user info returned after get_me")
            else: # Not authorized, try to reconnect and re-auth
                logger.warning("Ping: Not authorized. Attempting full reconnect cycle.")
                await client_instance.disconnect()
                await asyncio.sleep(5)
                await client_instance.connect()
                if not await client_instance.is_connected():
                    logger.error("Ping: Reconnect attempt failed.")
                    # Potentially trigger a restart or alert here if it keeps failing
                else: # Reconnected, now try to start (which includes auth)
                    logger.info("Ping: Reconnected, now attempting to re-authorize...")
                    await client_instance.start(phone=TG_PHONE) # Attempt re-auth
                    if await client_instance.is_user_authorized():
                        logger.info("Ping: Successfully reconnected and re-authorized.")
                    else:
                        logger.error("Ping: Re-authorization failed after reconnect.")
        except Exception as e:
            logger.error(f"Error during ping or reconnection attempt: {str(e)}", exc_info=True)
            # Basic backoff before next cycle if major error in ping
            await asyncio.sleep(60) 
        await asyncio.sleep(300) # 5 minutes

async def process_recent_messages(client, count):
    """Process a specified number of recent messages from source channel"""
    try:
        logger.info(f"Processing {count} recent messages from {SRC_CHANNEL}")
        
        # Get the most recent messages from source channel
        messages = await client.get_messages(SRC_CHANNEL, limit=count)
        
        # Process each message, starting from oldest (reverse order)
        for msg in reversed(messages):
            if not msg.text:
                continue
            
            # Extract URLs from message entities
            message_entity_urls = []
            if hasattr(msg, 'entities') and msg.entities:
                for entity in msg.entities:
                    if hasattr(entity, 'url') and entity.url:
                        message_entity_urls.append(entity.url)
                    elif hasattr(entity, '_') and entity._ in ('MessageEntityUrl', 'MessageEntityTextUrl'):
                        if hasattr(entity, 'offset') and hasattr(entity, 'length'):
                            url_text = msg.text[entity.offset:entity.offset + entity.length]
                            if url_text.startswith('http'):
                                message_entity_urls.append(url_text)
            
            logger.info(f"Processing message ID: {msg.id}")
            await translate_and_post(client, msg.text, msg.id, message_entity_urls=message_entity_urls)
            
            # Add a short delay between processing messages
            await asyncio.sleep(1)
            
        logger.info(f"Completed processing {count} recent messages")
        return True
    except Exception as e:
        logger.exception(f"Error processing recent messages: {e}")
        return False

async def background_keep_alive(client):
    """Background task to keep the connection alive and ensure updates are received"""
    logger.info("Starting background keep-alive task")
    count = 0
    
    while True:
        try:
            # Update online status to ensure Telegram knows we're active
            await client(UpdateStatusRequest(offline=False))
            
            # Log less frequently to reduce noise, only every 5 times
            count += 1
            if count % 5 == 1:
                logger.info("Connection keep-alive: online status updated")
                # Add a test entry to show we're actively running
                logger.info(f"Bot active and monitoring channel: {SRC_CHANNEL} → {DST_CHANNEL}")
            else:
                logger.debug("Connection keep-alive ping sent")
            
            # Sleep until next interval
            await asyncio.sleep(KEEP_ALIVE_INTERVAL)
        except Exception as e:
            logger.error(f"Error in keep-alive task: {e}")
            await asyncio.sleep(30)  # Shorter sleep on error

async def background_update_checker(client):
    """Background task to manually check for updates in case event handlers miss them"""
    logger.info("Starting background update checker task")
    last_check_time = datetime.now()
    
    while True:
        try:
            # Force catch up to get any missed updates
            try:
                await client.catch_up()
                logger.debug("Force update catch-up completed")
            except Exception as e:
                logger.debug(f"Force update catch-up note: {e}")
            
            # Calculate time since last check
            now = datetime.now()
            time_since_check = (now - last_check_time).total_seconds()
            
            if time_since_check >= CHECK_CHANNEL_INTERVAL:
                logger.info(f"Checking for any missed messages (last check was {time_since_check:.1f} seconds ago)")
                
                # Get recent messages from source channel
                messages = await client.get_messages(SRC_CHANNEL, limit=5)
                
                # Find messages within the last check interval
                for msg in messages:
                    if not msg.text:
                        continue
                        
                    msg_time = msg.date.replace(tzinfo=None)  # Remove timezone for comparison
                    
                    # Check if this message is new since our last check
                    if (now - msg_time) < timedelta(seconds=CHECK_CHANNEL_INTERVAL * 1.1):
                        logger.info(f"Found possibly missed message ID: {msg.id} from {msg_time}")
                        
                        # Check if message was already processed by checking recent posts in destination
                        dst_messages = await client.get_messages(DST_CHANNEL, limit=10)
                        already_processed = False
                        
                        # Simple content-based check (could be improved)
                        for dst_msg in dst_messages:
                            if dst_msg.text and msg.text[:50] in dst_msg.text:
                                already_processed = True
                                break
                                
                        if not already_processed:
                            # Extract URLs from message entities
                            message_entity_urls = []
                            if hasattr(msg, 'entities') and msg.entities:
                                for entity in msg.entities:
                                    if hasattr(entity, 'url') and entity.url:
                                        message_entity_urls.append(entity.url)
                                    elif hasattr(entity, '_') and entity._ in ('MessageEntityUrl', 'MessageEntityTextUrl'):
                                        if hasattr(entity, 'offset') and hasattr(entity, 'length'):
                                            url_text = msg.text[entity.offset:entity.offset + entity.length]
                                            if url_text.startswith('http'):
                                                message_entity_urls.append(url_text)
                            
                            logger.info(f"Processing potentially missed message ID: {msg.id}")
                            await translate_and_post(client, msg.text, msg.id, message_entity_urls=message_entity_urls)
                
                # Update last check time
                last_check_time = now
                logger.info("Missed message check completed")
            
            # Sleep until next manual poll cycle
            await asyncio.sleep(MANUAL_POLL_INTERVAL)
        except Exception as e:
            logger.error(f"Error in update checker: {e}")
            await asyncio.sleep(60)  # Sleep on error before retry

async def background_channel_poller(client):
    """Background task to manually poll for channel updates using GetChannelDifferenceRequest"""
    logger.info("Starting background channel polling task")
    first_run = True
    
    while True:
        try:
            # Get channel entity
            channel = await client.get_entity(SRC_CHANNEL)
            
            # Create input channel
            input_channel = InputChannel(channel_id=channel.id, access_hash=channel.access_hash)
            
            # Get stored pts value or use 0 for first run
            state = load_app_state()
            pts = state.get("pts", 0)
            
            # Get channel difference (manual poll for updates)
            try:
                logger.debug(f"Polling channel with pts={pts}")
                diff = await client(GetChannelDifferenceRequest(
                    channel=input_channel,
                    filter=ChannelMessagesFilterEmpty(),
                    pts=pts,  # Use stored pts value instead of hardcoded 0
                    limit=100
                ))
                
                logger.info(f"Channel polling: received {len(getattr(diff, 'new_messages', []))} new messages")
                
                # Update pts value if available
                if hasattr(diff, 'pts'):
                    update_pts(diff.pts)
                    logger.debug(f"Updated pts value to {diff.pts}")
                
                # Process any new messages found
                for new_msg in getattr(diff, 'new_messages', []):
                    if hasattr(new_msg, 'message') and new_msg.message:
                        # Extract URLs from message entities
                        message_entity_urls = []
                        if hasattr(new_msg, 'entities') and new_msg.entities:
                            for entity in new_msg.entities:
                                if hasattr(entity, 'url') and entity.url:
                                    message_entity_urls.append(entity.url)
                                elif hasattr(entity, '_') and entity._ in ('MessageEntityUrl', 'MessageEntityTextUrl'):
                                    if hasattr(entity, 'offset') and hasattr(entity, 'length'):
                                        url_text = new_msg.message[entity.offset:entity.offset + entity.length]
                                        if url_text.startswith('http'):
                                            message_entity_urls.append(url_text)
                        
                        logger.info(f"Processing newly discovered message from poll: {new_msg.id}")
                        await translate_and_post(client, new_msg.message, new_msg.id, message_entity_urls=message_entity_urls)
                        
                first_run = False  # Successfully completed a poll
                
            except Exception as e:
                # Handle the specific "Persistent timestamp empty" error differently
                if "Persistent timestamp empty" in str(e):
                    if first_run:
                        # It's normal on first run, so just log as info
                        logger.info("First-time channel polling initialization (this is normal)")
                        first_run = False
                    else:
                        # On subsequent runs, downgrade to debug level
                        logger.debug("Channel polling initialization step")
                else:
                    # This is an actual error we want to see
                    logger.error(f"Error in channel polling: {e}")
            
            # Sleep between polls
            await asyncio.sleep(MANUAL_POLL_INTERVAL)
        except Exception as e:
            logger.error(f"Error setting up channel polling: {e}")
            await asyncio.sleep(60)  # Sleep on error

async def poll_big_channel(client, channel_username):
    """
    Reliably polls a large channel for new messages using GetChannelDifference.
    Uses PTS (Points) to keep track of the current position in the update stream.
    Processes new messages found and updates PTS.
    """
    logger.info(f"Starting to poll channel: {channel_username}")
    
    try:
        entity = await client.get_entity(channel_username)
        input_channel = InputChannel(channel_id=entity.id, access_hash=entity.access_hash)
        logger.info(f"Successfully resolved channel: {channel_username} to ID: {entity.id}")

        # Load initial PTS from global app state
        current_app_state = load_app_state()
        last_pts = current_app_state.get('pts', 0)
        if last_pts == 0:
            try:
                # If PTS is not available, get latest message
                logger.info("No PTS available in app state for this channel. Getting latest message...")
                messages = await client.get_messages(channel_username, limit=1)
                if messages and len(messages) > 0:
                    msg = messages[0]
                    logger.info(f"Latest message ID: {msg.id}")
                    
                    # Extract URLs from message entities
                    message_entity_urls = []
                    if hasattr(msg, 'entities') and msg.entities:
                        for entity in msg.entities:
                            if hasattr(entity, 'url') and entity.url:
                                message_entity_urls.append(entity.url)
                            elif hasattr(entity, '_') and entity._ in ('MessageEntityUrl', 'MessageEntityTextUrl'):
                                if hasattr(entity, 'offset') and hasattr(entity, 'length'):
                                    url_text = msg.text[entity.offset:entity.offset + entity.length]
                                    if url_text.startswith('http'):
                                        message_entity_urls.append(url_text)
                    
                    # Process this latest message if it has text
                    # In test mode, only process if it contains the test prefix
                    test_prefix = os.getenv('TEST_RUN_MESSAGE_PREFIX')
                    if msg.text and (not test_prefix or test_prefix in msg.text):
                        await translate_and_post(client, msg.text, msg.id, message_entity_urls=message_entity_urls)
                    elif test_prefix and msg.text:
                        logger.info(f"Test mode: Skipping latest message ID {msg.id} (no test prefix)")
                    
                    # Try to get the dialog to get PTS
                    dialogs = await client.get_dialogs()
                    for dialog in dialogs:
                        if hasattr(dialog, 'entity') and hasattr(dialog.entity, 'id') and dialog.entity.id == entity.id:
                            if hasattr(dialog, 'dialog') and hasattr(dialog.dialog, 'pts'):
                                initial_pts = dialog.dialog.pts
                                logger.info(f"Got initial PTS {initial_pts} from dialog")
                                last_pts = initial_pts
                                # Update app state with this PTS
                                current_app_state['pts'] = initial_pts
                                save_app_state(current_app_state)
                                break
                else:
                    logger.warning(f"No messages found in channel {channel_username}")
            except Exception as e:
                logger.error(f"Error initializing PTS: {e}")
        else:
            logger.info(f"Using PTS from app state: {last_pts}")

        # Main polling loop
        processing_message = False  # Flag to prevent database locks
        while True:
            if processing_message:
                # If we're currently processing a message, wait before polling again
                # This helps prevent database locks from concurrent access to the session file
                await asyncio.sleep(1)
                continue
                
            try:
                # Get channel difference with current PTS
                channel_diff = await client(GetChannelDifferenceRequest(
                    channel=input_channel,
                    filter=ChannelMessagesFilterEmpty(),
                    pts=last_pts,
                    limit=100
                ))
                
                # Update PTS from response
                if hasattr(channel_diff, 'pts'):
                    new_pts = channel_diff.pts
                    logger.info(f"Channel difference PTS: {new_pts}")
                    
                    # Only update app state if PTS changed
                    if new_pts != last_pts:
                        last_pts = new_pts
                        current_app_state['pts'] = new_pts
                        save_app_state(current_app_state)
                
                # Process new messages
                if hasattr(channel_diff, 'new_messages'):
                    logger.info(f"Channel difference returned {len(channel_diff.new_messages)} new messages")
                    
                    # In test mode, only process messages with the test prefix
                    test_prefix = os.getenv('TEST_RUN_MESSAGE_PREFIX')
                    if test_prefix:
                        logger.info(f"Test mode: Looking for messages with prefix '{test_prefix}'")
                    
                    for msg in channel_diff.new_messages:
                        if hasattr(msg, 'message') and msg.message:
                            # In test mode, skip messages that don't have the test prefix
                            if test_prefix and test_prefix not in msg.message:
                                logger.info(f"Test mode: Skipping message ID {msg.id} (no test prefix)")
                                continue
                                
                            logger.info(f"Processing new message ID: {msg.id}")
                            processing_message = True
                            
                            # Extract URLs from message entities
                            message_entity_urls = []
                            if hasattr(msg, 'entities') and msg.entities:
                                for entity in msg.entities:
                                    if hasattr(entity, 'url') and entity.url:
                                        message_entity_urls.append(entity.url)
                                    elif hasattr(entity, '_') and entity._ in ('MessageEntityUrl', 'MessageEntityTextUrl'):
                                        if hasattr(entity, 'offset') and hasattr(entity, 'length'):
                                            url_text = msg.message[entity.offset:entity.offset + entity.length]
                                            if url_text.startswith('http'):
                                                message_entity_urls.append(url_text)
                            
                            # Process the message
                            await translate_and_post(client, msg.message, msg.id, message_entity_urls=message_entity_urls)
                            processing_message = False
                
                # Use recommended timeout or default interval
                timeout = getattr(channel_diff, 'timeout', MANUAL_POLL_INTERVAL)
                await asyncio.sleep(timeout)
                
            except Exception as e:
                processing_message = False
                if "database is locked" in str(e).lower():
                    logger.warning(f"Database lock detected in poll_big_channel, sleeping longer: {e}")
                    await asyncio.sleep(120)  # Sleep longer to let locks clear
                else:
                    logger.error(f"Error in poll_big_channel: {e}", exc_info=True)
                    await asyncio.sleep(30)
    except Exception as e:
        logger.error(f"Fatal error in poll_big_channel: {e}", exc_info=True)

async def main():
    """
    Main entry point for the Zoomer Bot.
    Sets up Telegram client, event handlers, and starts the client.
    """
    parser = argparse.ArgumentParser(description='Telegram Zoomer Bot - Translate messages with Artemiy Lebedev style')
    parser.add_argument('--process-recent', type=int, help='Process the specified number of recent messages')
    args = parser.parse_args()
    
    try:
        # Create Telegram client
        logger.info(f"Creating Telegram client with session: {SESSION}")
        client = TelegramClient(
            SESSION,
            int(API_ID), 
            API_HASH,
            connection=ConnectionTcpAbridged
        )
        
        # Set up event handler
        @client.on(events.NewMessage(chats=SRC_CHANNEL))
        async def handler(event):
            txt = event.message.text
            if not txt: return
            logger.info(f"Received new message: {txt[:50]}...")
            
            # Extract URLs from message entities
            message_entity_urls = []
            if hasattr(event.message, 'entities') and event.message.entities:
                for entity in event.message.entities:
                    if hasattr(entity, 'url') and entity.url:
                        message_entity_urls.append(entity.url)
                    elif hasattr(entity, '_') and entity._ in ('MessageEntityUrl', 'MessageEntityTextUrl'):
                        if hasattr(entity, 'offset') and hasattr(entity, 'length'):
                            url_text = txt[entity.offset:entity.offset + entity.length]
                            if url_text.startswith('http'):
                                message_entity_urls.append(url_text)
            
            await translate_and_post(client, event.message.text, event.message.id, message_entity_urls=message_entity_urls)
        
        # Connect to Telegram
        logger.info("Starting Telegram client...")
        await client.start(phone=TG_PHONE)
        
        # Process recent messages if requested
        if args.process_recent and args.process_recent > 0:
            logger.info(f"Processing {args.process_recent} recent messages")
            messages = await client.get_messages(SRC_CHANNEL, limit=args.process_recent)
            
            # Process each message
            for msg in reversed(messages):
                logger.info(f"Processing message ID: {msg.id}")
                if not msg.text: continue
                
                # Extract URLs from message entities
                message_entity_urls = []
                if hasattr(msg, 'entities') and msg.entities:
                    for entity in msg.entities:
                        if hasattr(entity, 'url') and entity.url:
                            message_entity_urls.append(entity.url)
                        elif hasattr(entity, '_') and entity._ in ('MessageEntityUrl', 'MessageEntityTextUrl'):
                            if hasattr(entity, 'offset') and hasattr(entity, 'length'):
                                url_text = msg.text[entity.offset:entity.offset + entity.length]
                                if url_text.startswith('http'):
                                    message_entity_urls.append(url_text)
                
                await translate_and_post(client, msg.text, msg.id, message_entity_urls=message_entity_urls)
                await asyncio.sleep(2)  # Add delay between processing
            
            logger.info("Finished processing recent messages")
        
        # Run the client in mega-channel short-poll mode
        logger.info(f"Client ready, polling channel: {SRC_CHANNEL}")
        await poll_big_channel(client, SRC_CHANNEL)
        
    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 