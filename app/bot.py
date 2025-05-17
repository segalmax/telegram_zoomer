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
import openai
from dotenv import load_dotenv
from .translator import get_openai_client, translate_text
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
SESSION_PATH = os.getenv('TG_SESSION', 'session/nyt_zoomer')
SRC_CHANNEL = os.getenv('SRC_CHANNEL')
DST_CHANNEL = os.getenv('DST_CHANNEL')
TRANSLATION_STYLE = os.getenv('TRANSLATION_STYLE', 'right')  # right only by default
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
    OPENAI_KEY = os.getenv('OPENAI_API_KEY')
except (TypeError, ValueError) as e:
    logger.error(f"Error: TG_API_ID, TG_API_HASH, or OPENAI_API_KEY is not set correctly in .env: {e}")
    sys.exit("Critical environment variables missing or invalid. Exiting.")

TG_PHONE = os.getenv('TG_PHONE') # Optional, bot will prompt

# Use session manager to handle session persistence
SESSION = setup_session()

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
        image_url_str = None  # Renamed from image_url to avoid confusion
        
        # Re-evaluate GENERATE_IMAGES at runtime so that tests
        # can control it via environment variables _after_ this module
        # has already been imported.
        generate_images = os.getenv("GENERATE_IMAGES", "true").lower() == "true"

        if generate_images and openai_client:
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
        elif not openai_client and generate_images:
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

        # Use only RIGHT style - much simpler logic
        if not openai_client:
            logger.error("Cannot translate without OpenAI client.")
            return False
        
        # Only support right style
        logger.info("Translating in RIGHT-BIDLO style...")
        translated_text = await translate_text(openai_client, txt, 'right')
        
        # Combine header with translated content instead of sending separately
        full_content = f"🔴 RIGHT-BIDLO VERSION:\n\n{translated_text}"
        await send_message_parts(dst_channel_to_use, full_content, image_data, image_url_str)
        logger.info(f"Posted right-bidlo version")
        
        # Store the message ID and timestamp for recovery after restarts
        # This responsibility is moved to the caller (e.g., poll_big_channel or handle_new_message)
        # if message_id is not None:
        #     try:
        #         message = await client_instance.get_messages(SRC_CHANNEL, ids=message_id)
        #         if message and hasattr(message, 'date'):
        #             # OLD: save_last_processed_state(message_id, message.date)
        #             pass # State saving handled by caller
        #         else:
        #             # OLD: save_last_processed_state(message_id, datetime.now())
        #             pass # State saving handled by caller
        #     except Exception as e:
        #         logger.warning(f"Could not get message date for ID {message_id}: {e}")
        #         # OLD: save_last_processed_state(message_id, datetime.now())
        #         pass # State saving handled by caller
        
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
            success = await translate_and_post(client_instance, txt, event.message.id)
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
            logger.info(f"No previous PTS found for channel {entity.id}, starting from latest state.")
            # Get current PTS state if starting from scratch
            try:
                # Attempt to get current state to initialize PTS correctly
                # This is a common pattern to get the initial PTS for a channel.
                # We fetch no messages (limit=0) just to get the current pts from the state.
                initial_diff = await client(GetChannelDifferenceRequest(
                    channel=input_channel,
                    filter=ChannelMessagesFilterEmpty(), # No specific filter, just want state
                    pts=1, # Smallest possible PTS to ensure we get current state
                    limit=0 # Don't need messages, just the state object for its PTS
                ))
                if hasattr(initial_diff, 'pts'):
                    last_pts = initial_diff.pts
                    current_app_state['pts'] = last_pts
                    current_app_state['channel_id'] = entity.id # Store channel ID if not already there
                    save_app_state(current_app_state)
                    logger.info(f"Initialized PTS for channel {entity.id} to {last_pts}.")
                elif hasattr(initial_diff, 'new_messages') and not initial_diff.new_messages and hasattr(initial_diff, 'final') and initial_diff.final:
                    # This might be a ChannelDifferenceEmpty, meaning we are up to date, PTS is in other_updates or not needed.
                    # Or it could be ChannelDifferenceTooLong. If too long, we need to fetch initial messages.
                    logger.info("Initial GetChannelDifference returned empty or final state. Assuming up-to-date or will catch up.")
                    # If it was ChannelDifferenceTooLong, the next loop iteration will handle it.
                    # For safety, ensure last_pts is not 0 if we can find a message
                    async for m in client.iter_messages(input_channel, limit=1):
                        if m and hasattr(m, 'pts'): 
                            last_pts = m.pts 
                            current_app_state['pts'] = last_pts
                            save_app_state(current_app_state)
                            logger.info(f"Set initial PTS from latest message: {last_pts}")
                        break # only need one
                    if last_pts == 0: # if channel is empty or no pts on message
                        last_pts = 1 # Start with 1 if truly nothing found
                        logger.warning("Could not determine initial PTS, starting with 1. This might re-process if channel is very old & empty.")

            except Exception as e:
                logger.error(f"Error getting initial PTS for {channel_username}: {e}. Will use last known PTS or 0.")
        
        logger.info(f"Initial PTS for channel {entity.id}: {last_pts}")

    except ValueError as e:
        logger.error(f"Channel {channel_username} not found or invalid: {e}")
        return
    except Exception as e:
        logger.error(f"Error setting up poller for {channel_username}: {e}", exc_info=True)
        return

    max_retries = 5
    retry_delay = 10  # seconds

    while True:
        retries = 0
        processed_messages_in_cycle = 0
        try:
            logger.debug(f"Polling {channel_username} (ID: {entity.id}) with PTS: {last_pts}")
            
            # Get updates (difference) since the last PTS
            # Limit can be adjusted; 100 is a common default.
            difference = await client(GetChannelDifferenceRequest(
                channel=input_channel,
                filter=ChannelMessagesFilterEmpty(), # No specific filter, interested in all new messages
                pts=last_pts,
                limit=100  # Max messages to fetch per request
            ))

            # Process the difference object
            if hasattr(difference, 'new_messages') and difference.new_messages:
                logger.info(f"Found {len(difference.new_messages)} new messages in {channel_username}.")
                # Sort messages by date/ID to process in order
                sorted_messages = sorted(difference.new_messages, key=lambda m: (m.date, m.id))
                
                for message in sorted_messages:
                    if not hasattr(message, 'message') or not message.message: # Skip non-text or empty messages
                        if hasattr(message, 'pts') and message.pts:
                            last_pts = message.pts # Update PTS even for skipped messages
                        continue

                    txt_to_process = message.message
                    logger.info(f"Processing message ID {message.id} from {channel_username}: {txt_to_process[:50]}...")
                    
                    success = await translate_and_post(client, txt_to_process, message.id, DST_CHANNEL)
                    if success:
                        processed_messages_in_cycle += 1
                        current_app_state = load_app_state() # Reload state before updating
                        current_app_state['message_id'] = message.id
                        current_app_state['timestamp'] = message.date.isoformat()
                        if hasattr(message, 'pts') and message.pts: # Update PTS from message if available
                            last_pts = message.pts 
                            current_app_state['pts'] = last_pts
                        # Also update channel_id if it's missing, though it should be set by now
                        if 'channel_id' not in current_app_state or not current_app_state['channel_id']:
                            current_app_state['channel_id'] = entity.id
                        save_app_state(current_app_state)
                        logger.info(f"App state updated. Last processed ID: {message.id}, New PTS for {entity.id}: {last_pts}")
                    else:
                        logger.warning(f"Failed to process message ID {message.id} from {channel_username}. It might be retried if PTS doesn't advance.")
                        # If processing fails, we might not want to advance PTS past this message
                        # or implement a more robust retry/skip mechanism.
                        # For now, PTS will be updated from the GetChannelDifference result's PTS later.

            # Update PTS from the difference object itself (this is the most reliable PTS)
            if hasattr(difference, 'pts'):
                if difference.pts > last_pts:
                    logger.info(f"Updating PTS for channel {entity.id} from {last_pts} to {difference.pts} (from GetChannelDifference response)")
                    last_pts = difference.pts
                    # Save the new PTS immediately
                    current_app_state = load_app_state()
                    current_app_state['pts'] = last_pts
                    current_app_state['channel_id'] = entity.id # Ensure channel_id is also persisted with PTS
                    save_app_state(current_app_state)
                elif difference.pts < last_pts:
                    logger.warning(f"PTS from GetChannelDifference ({difference.pts}) is less than current PTS ({last_pts}). This should not happen. Not updating PTS.")
            elif hasattr(difference, 'intermediate_state') and hasattr(difference.intermediate_state, 'pts'): # For ChannelDifference
                 if difference.intermediate_state.pts > last_pts:
                    logger.info(f"Updating PTS for channel {entity.id} from {last_pts} to {difference.intermediate_state.pts} (from ChannelDifference intermediate_state)")
                    last_pts = difference.intermediate_state.pts
                    current_app_state = load_app_state()
                    current_app_state['pts'] = last_pts
                    current_app_state['channel_id'] = entity.id
                    save_app_state(current_app_state)
            # No new messages and PTS is the same means we are up to date for this slice
            elif not hasattr(difference, 'new_messages') or not difference.new_messages:
                logger.debug(f"No new messages in {channel_username} for PTS {last_pts}.")
            
            # Handle ChannelDifferenceTooLong: we need to fetch messages iteratively
            # This basic poller might not fully handle ChannelDifferenceTooLong if it means there are more than 'limit' messages
            # A robust solution for TooLong might involve fetching messages until caught up before relying on GetChannelDifference again.
            # However, Telethon's GetChannelDifference is meant to handle this by returning a state from which to continue.
            # If difference.final is False and there are other_updates, it means there's more to fetch.
            if hasattr(difference, 'final') and not difference.final and (hasattr(difference, 'other_updates') and difference.other_updates):
                 logger.info(f"More updates available for {channel_username} (final=false). Continuing polling immediately.")
                 # No sleep, continue to fetch next batch
                 continue 

            if processed_messages_in_cycle == 0:
                 logger.debug(f"No messages processed in this cycle for {channel_username}.")
            
            # Wait before the next poll
            await asyncio.sleep(MANUAL_POLL_INTERVAL) 
            retries = 0 # Reset retries on successful poll

        except ConnectionError as e:
            retries += 1
            logger.error(f"Connection error polling {channel_username} (attempt {retries}/{max_retries}): {e}")
            if retries >= max_retries:
                logger.error(f"Max retries reached for {channel_username}. Stopping polling for this channel.")
                # Consider a mechanism to restart the bot or this specific task after a longer delay
                # For now, this task will exit.
                break 
            logger.info(f"Retrying in {retry_delay} seconds...")
            await asyncio.sleep(retry_delay)
            # Attempt to reconnect before next retry
            if not client.is_connected():
                try:
                    logger.info("Attempting to reconnect client...")
                    await client.connect()
                    if await client.is_connected():
                        logger.info("Client reconnected successfully.")
                    else:
                        logger.error("Failed to reconnect client.")
                        # If reconnect fails, it might be better to let the main loop handle this or exit.
                except Exception as ce:
                    logger.error(f"Exception during reconnection attempt: {ce}")
        
        except Exception as e:
            logger.error(f"An unexpected error occurred in poll_big_channel for {channel_username}: {e}", exc_info=True)
            # General error, wait and retry
            await asyncio.sleep(MANUAL_POLL_INTERVAL * 2) # Longer delay for unexpected errors

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
    
    # Parse command line arguments first to handle process-recent
    parser = argparse.ArgumentParser(description='Telegram Zoomer Bot')
    parser.add_argument('--process-recent', type=int, help='Process N recent messages from the source channel')
    parser.add_argument('--timeout', type=int, default=30, help='Connection timeout in seconds')
    args = parser.parse_args()
    
    # Set timeout from arguments or default
    connection_timeout = args.timeout if args.timeout else 30
    logger.info(f"Using connection timeout of {connection_timeout} seconds")
    
    # Set up connection parameters with fallbacks
    connection_types = [ConnectionTcpAbridged, ConnectionTcpIntermediate, ConnectionTcpFull]
    
    # Try different connection types until one works
    client = None
    connected = False
    
    for connection_type in connection_types:
        connection_name = connection_type.__name__
        logger.info(f"Trying connection type: {connection_name}")
        
        # Create a new client with this connection type
        try:
            # Use a custom connection with configurable parameters
            client = TelegramClient(
                SESSION_PATH,
                API_ID, 
                API_HASH,
                connection=connection_type,
                use_ipv6=False,
                timeout=connection_timeout,
                retry_delay=1,
                auto_reconnect=True,
                sequential_updates=True,
                flood_sleep_threshold=60
            )
            
            # Try to connect with timeout
            logger.info(f"Connecting with timeout {connection_timeout}s...")
            try:
                # Use asyncio.wait_for to enforce a timeout
                await asyncio.wait_for(
                    client.connect(),
                    timeout=connection_timeout
                )
            except asyncio.TimeoutError:
                logger.warning(f"Connection timed out after {connection_timeout}s")
                if client: await client.disconnect()
                continue
            except Exception as e:
                logger.warning(f"Connection error: {str(e)}")
                if client: await client.disconnect()
                continue
            
            # Check if connection succeeded
            if client.is_connected():
                logger.info("Successfully connected to Telegram")
                connected = True
                break
            else:
                logger.warning("Failed to connect")
                if client: await client.disconnect()
                
        except Exception as e:
            logger.warning(f"Error setting up connection: {str(e)}")
            if client: 
                try: await client.disconnect()
                except: pass
    
    # If we couldn't connect with any method, exit
    if not connected or not client:
        logger.error("Failed to connect to Telegram with any connection method. Please check your network.")
        return False
    
    # Now try to authenticate
    try:
        if await client.is_user_authorized():
            logger.info("Successfully authenticated using saved session")
        else:
            # If not authorized, then try regular authentication
            logger.info("Saved session not valid, attempting phone authentication...")
            await client.start(phone=PHONE)
    except Exception as e:
        logger.error(f"Error authenticating: {str(e)}")
        await client.disconnect()
        return False
    
    logger.info("Client started successfully")
    
    # Check if user is authorized
    if not await client.is_user_authorized():
        logger.error("User is not authorized. Please check your session file or authentication.")
        await client.disconnect()
        return False
    
    # Handle the --process-recent argument
    if args.process_recent:
        success = await process_recent_messages(client, args.process_recent)
        await client.disconnect()
        return success
    
    # Register event handler for new messages
    @client.on(events.NewMessage(chats=SRC_CHANNEL))
    async def handler(event):
        logger.info(f"New message event received from {SRC_CHANNEL}, ID: {event.message.id}")
        await translate_and_post(client, event.message.text, event.message.id)
    
    # Start the proper megachannel polling task
    asyncio.create_task(poll_big_channel(client, SRC_CHANNEL))
    
    logger.info(f"Bot is now running, listening to {SRC_CHANNEL}")
    logger.info(f"Translation style: {TRANSLATION_STYLE}")
    logger.info(f"Image generation: {'Enabled' if GENERATE_IMAGES else 'Disabled'}")
    
    # Force initial catch up to ensure we're getting updates
    try:
        await asyncio.wait_for(client.catch_up(), timeout=30)
        logger.info("Initial catch-up completed")
    except asyncio.TimeoutError:
        logger.warning("Initial catch-up timed out, continuing anyway")
    except Exception as e:
        logger.warning(f"Error during initial catch-up: {e}, continuing anyway")
    
    # Check for missed messages during downtime
    try:
        state = load_app_state()
        if state and state.get("message_id", 0) > 0:
            logger.info(f"Checking for missed messages since last processed message ID: {state.get('message_id')}")
            
            # Get messages newer than our last processed message
            messages = await client.get_messages(
                SRC_CHANNEL,
                min_id=state.get("message_id"),
                limit=10
            )
            
            if messages:
                logger.info(f"Found {len(messages)} potentially missed messages during downtime")
                # Process them in order from oldest to newest
                for msg in reversed(messages):
                    if not msg.text:
                        continue
                    logger.info(f"Processing missed message from downtime recovery: ID {msg.id}")
                    await translate_and_post(client, msg.text, msg.id)
                    await asyncio.sleep(1)  # Small delay to prevent rate limiting
            else:
                logger.info("No missed messages found during downtime")
    except Exception as e:
        logger.error(f"Error checking for missed messages: {e}", exc_info=True)
    
    # Keep the connection running
    await client.run_until_disconnected()
    return True

if __name__ == "__main__":
    asyncio.run(main()) 