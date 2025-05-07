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
from telethon.network import ConnectionTcpAbridged
import openai
from dotenv import load_dotenv
from .translator import get_openai_client, translate_text
from .image_generator import generate_image_for_post
from telethon.tl.functions.account import UpdateStatusRequest
from telethon.tl.functions.updates import GetChannelDifferenceRequest
from telethon.tl.types import InputChannel, ChannelMessagesFilterEmpty
from telethon.errors import SessionPasswordNeededError
from datetime import datetime, timedelta
import random
import argparse

# Load environment variables explicitly from project root
dotenv_path = Path(__file__).resolve().parent.parent / '.env'
if dotenv_path.exists():
    load_dotenv(dotenv_path=dotenv_path)
else:
    print(f"Warning: .env file not found at {dotenv_path}", file=sys.stderr)

# Get configuration from environment variables
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
PHONE = os.getenv('PHONE') or os.getenv('TG_PHONE')  # Check both variable names
SESSION_PATH = os.getenv('SESSION_PATH', 'session/nyt_zoomer')
SRC_CHANNEL = os.getenv('SRC_CHANNEL')
DST_CHANNEL = os.getenv('DST_CHANNEL')
TRANSLATION_STYLE = os.getenv('TRANSLATION_STYLE', 'both')  # left, right, both
GENERATE_IMAGES = os.getenv('GENERATE_IMAGES', 'true').lower() == 'true'
OPENAI_KEY = os.getenv('OPENAI_API_KEY')
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

# Configuration from environment variables
try:
    API_ID = int(os.getenv('TG_API_ID'))
    API_HASH = os.getenv('TG_API_HASH')
    OPENAI_KEY = os.getenv('OPENAI_API_KEY')
except (TypeError, ValueError) as e:
    logger.error(f"Error: TG_API_ID, TG_API_HASH, or OPENAI_API_KEY is not set correctly in .env: {e}")
    sys.exit("Critical environment variables missing or invalid. Exiting.")

TG_PHONE = os.getenv('TG_PHONE') # Optional, bot will prompt
SESSION_DEFAULT = 'session/new_session' if (Path(__file__).resolve().parent.parent / 'session').is_dir() else 'new_session'
SESSION = os.getenv('TG_SESSION', SESSION_DEFAULT)

if not SRC_CHANNEL or not DST_CHANNEL:
    logger.error("Error: SRC_CHANNEL or DST_CHANNEL is not set in .env.")
    sys.exit("Source/Destination channel environment variables missing. Exiting.")

# Initialize OpenAI client
openai_client = None
if OPENAI_KEY:
    openai_client = get_openai_client(OPENAI_KEY)
else:
    logger.error("OPENAI_API_KEY not found. OpenAI related functions will fail.")
    # Decide if this is fatal or if bot can run without OpenAI (e.g. only relaying)

async def translate_and_post(client_instance, txt, message_id=None, destination_channel=None):
    # Renamed client to client_instance to avoid conflict with openai_client module
    try:
        start_time = time.time()
        logger.info(f"Starting translation and posting for message ID: {message_id}")
        
        dst_channel_to_use = destination_channel or DST_CHANNEL
        logger.info(f"Using destination channel: {dst_channel_to_use}")
        
        image_data = None
        image_url_str = None # Renamed from image_url to avoid confusion
        
        if GENERATE_IMAGES and openai_client:
            logger.info("Generating image for post...")
            result = await generate_image_for_post(openai_client, txt)
            if result:
                if isinstance(result, str):
                    image_url_str = result
                    logger.info("Using image URL instead of direct upload")
                else:
                    image_data = result
                    logger.info("Image data received successfully")
            else:
                logger.warning("No image result was returned")
        elif not openai_client and GENERATE_IMAGES:
            logger.warning("Image generation is enabled, but OpenAI client is not initialized (missing API key?).")

        # Always include source attribution, even when URL is not available
        source_footer = f"\n\n🔗 Оригинал: {extract_nytimes_link(txt)}" if extract_nytimes_link(txt) else "\n\n🔗 Оригинал: Unknown source"
        
        async def send_message_parts(channel, text_content, image_file=None, image_url_link=None):
            if image_file:
                # Use up to 1024 characters for caption
                caption = text_content[:1024]
                await client_instance.send_file(channel, image_file, caption=caption)
                # If text is too long for caption, send the rest as a separate message
                if len(text_content) > 1024:
                    remaining_text = text_content[1024:]
                    if remaining_text.strip(): # ensure remaining_text actually has content
                        await client_instance.send_message(channel, remaining_text)
            elif image_url_link:
                full_message = f"{text_content}\\n\\n🖼️ {image_url_link}"
                await client_instance.send_message(channel, full_message)
            else:
                await client_instance.send_message(channel, text_content)

        if TRANSLATION_STYLE == 'both':
            if not openai_client:
                logger.error("Cannot translate in 'both' style without OpenAI client.")
                return False
            logger.info("Translating in LEFT style...")
            left = await translate_text(openai_client, txt, 'left')
            logger.info("Posting LEFT translation...")
            await client_instance.send_message(dst_channel_to_use, "🟢 LEFT-ZOOMER VERSION:")
            await send_message_parts(dst_channel_to_use, left, image_data, image_url_str)
            logger.info("Posted left-leaning version")

            logger.info("Translating in RIGHT style...")
            right = await translate_text(openai_client, txt, 'right')
            logger.info("Posting RIGHT translation...")
            await client_instance.send_message(dst_channel_to_use, "🔴 RIGHT-BIDLO VERSION:")
            await send_message_parts(dst_channel_to_use, right) # No image for the second part
            logger.info("Posted right-wing version")
        else: # 'left' or 'right'
            if not openai_client:
                logger.error(f"Cannot translate in '{TRANSLATION_STYLE}' style without OpenAI client.")
                return False
            style = TRANSLATION_STYLE
            logger.info(f"Translating in {style.upper()} style...")
            translated_text = await translate_text(openai_client, txt, style)
            header = "🟢 LEFT-ZOOMER VERSION:" if style == 'left' else "🔴 RIGHT-BIDLO VERSION:"
            await client_instance.send_message(dst_channel_to_use, header)
            await send_message_parts(dst_channel_to_use, translated_text, image_data, image_url_str)
            logger.info(f"Posted {style}-style version")
        
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
            logger.info(f"Processing new message: {txt[:50]}...")
            await translate_and_post(client_instance, txt, event.message.id)
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
            processing_msg_timeout = min(180, (timeout - (time.time() - start_time)) / (len(messages) - processed_count + 1))
            try:
                success = await asyncio.wait_for(
                    translate_and_post(client_instance, msg.text, msg.id),
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

def extract_nytimes_link(text):
    if not text: return None
    
    # Let the LLM handle URL extraction for more flexibility
    # The link will be included naturally in the translations based on our prompt
    return None

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
                
            logger.info(f"Processing message ID: {msg.id}")
            await translate_and_post(client, msg.text, msg.id)
            
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
                            logger.info(f"Processing potentially missed message ID: {msg.id}")
                            await translate_and_post(client, msg.text, msg.id)
                
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
            
            # Get channel difference (manual poll for updates)
            try:
                diff = await client(GetChannelDifferenceRequest(
                    channel=input_channel,
                    filter=ChannelMessagesFilterEmpty(),
                    pts=0,  # Start from beginning (this should be stored and incremented)
                    limit=100
                ))
                
                logger.info(f"Channel polling: received {len(getattr(diff, 'new_messages', []))} new messages")
                
                # Process any new messages found
                for new_msg in getattr(diff, 'new_messages', []):
                    if hasattr(new_msg, 'message') and new_msg.message:
                        logger.info(f"Processing newly discovered message from poll: {new_msg.id}")
                        await translate_and_post(client, new_msg.message, new_msg.id)
                        
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

async def main():
    """Main function to run the bot"""
    # Check if required environment variables are set
    if not all([API_ID, API_HASH, PHONE, SRC_CHANNEL, DST_CHANNEL]):
        logger.error("Missing required environment variables")
        for var in ['API_ID', 'API_HASH', 'PHONE', 'SRC_CHANNEL', 'DST_CHANNEL']:
            if not globals()[var]:
                logger.error(f"Missing {var}")
        return False
    
    # Create directories if they don't exist
    session_dir = Path(SESSION_PATH).parent
    session_dir.mkdir(exist_ok=True)
    
    # Create the client
    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
    
    # Start the client
    await client.start(phone=PHONE)
    logger.info("Client started successfully")
    
    # Check if user is authorized
    if not await client.is_user_authorized():
        logger.error("User is not authorized. Please check your session file or authentication.")
        return False
    
    # Handle the --process-recent argument
    parser = argparse.ArgumentParser(description='Telegram Zoomer Bot')
    parser.add_argument('--process-recent', type=int, help='Process N recent messages from the source channel')
    args = parser.parse_args()
    
    if args.process_recent:
        await process_recent_messages(client, args.process_recent)
        await client.disconnect()
        return True
    
    # Register event handler for new messages
    @client.on(events.NewMessage(chats=SRC_CHANNEL))
    async def handler(event):
        logger.info(f"New message event received from {SRC_CHANNEL}, ID: {event.message.id}")
        await translate_and_post(client, event.message.text, event.message.id)
    
    # Start background tasks for robust operation
    asyncio.create_task(background_keep_alive(client))
    asyncio.create_task(background_update_checker(client))
    asyncio.create_task(background_channel_poller(client))
    
    logger.info(f"Bot is now running, listening to {SRC_CHANNEL}")
    logger.info(f"Translation style: {TRANSLATION_STYLE}")
    logger.info(f"Image generation: {'Enabled' if GENERATE_IMAGES else 'Disabled'}")
    
    # Force initial catch up to ensure we're getting updates
    await client.catch_up()
    
    # Keep the connection running
    await client.run_until_disconnected()
    return True

if __name__ == "__main__":
    asyncio.run(main()) 