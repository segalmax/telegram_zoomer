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

# Load environment variables explicitly from project root
dotenv_path = Path(__file__).resolve().parent.parent / '.env'
if dotenv_path.exists():
    load_dotenv(dotenv_path=dotenv_path)
else:
    print(f"Warning: .env file not found at {dotenv_path}", file=sys.stderr)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
SRC_CHANNEL = os.getenv('SRC_CHANNEL')
DST_CHANNEL = os.getenv('DST_CHANNEL')

if not SRC_CHANNEL or not DST_CHANNEL:
    logger.error("Error: SRC_CHANNEL or DST_CHANNEL is not set in .env.")
    sys.exit("Source/Destination channel environment variables missing. Exiting.")

TRANSLATION_STYLE = os.getenv('TRANSLATION_STYLE', 'both')
GENERATE_IMAGES = os.getenv('GENERATE_IMAGES', 'true').lower() == 'true'
USE_STABILITY_AI = os.getenv('USE_STABILITY_AI', 'false').lower() == 'true'

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

        # The LLM will now handle source attribution naturally based on the prompt
        # No need for hardcoded source_footer
        
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

async def run_bot():
    logger.info("Starting Telegram Zoomer bot")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Using session file: {SESSION}")
    
    client = None # Keep 'client' as the variable name within this function scope for Telethon client
    try:
        client = TelegramClient(
            SESSION, API_ID, API_HASH,
            connection=ConnectionTcpAbridged,
            device_model="MacbookPro", system_version="macOS Ventura", app_version="ZoomerBot 1.0",
            receive_updates=True, auto_reconnect=True, retry_delay=5, connection_retries=10
        )
        logger.info("Connecting to Telegram...")
        try:
            await asyncio.wait_for(client.connect(), timeout=30)
        except asyncio.TimeoutError:
            logger.error("Timed out connecting to Telegram.")
            return
        logger.info("Connected successfully.")

        logger.info("Starting client and handling authentication if needed...")
        try:
            await client.start(phone=TG_PHONE) # TG_PHONE can be None, client.start handles it
        except asyncio.TimeoutError:
            logger.error("Timed out starting client (authentication step).")
            if client.is_connected(): await client.disconnect()
            return
        except Exception as e: # Other errors during start (e.g. invalid phone, API hash)
            logger.error(f"Error starting client: {str(e)}")
            if client.is_connected(): await client.disconnect()
            return
        
        if not await client.is_user_authorized():
            logger.error("Authentication failed. Please ensure credentials and code are correct.")
            if client.is_connected(): await client.disconnect()
            return
        logger.info("Successfully authorized - ready to process messages.")
                
        import argparse
        parser = argparse.ArgumentParser(description='Telegram NYT-to-Zoomer Bot')
        parser.add_argument('--process-recent', type=int, help='Process N most recent posts')
        args = parser.parse_args()
        
        if args.process_recent:
            logger.info(f"Batch mode: processing {args.process_recent} recent posts.")
            try:
                await process_recent_posts(client, limit=args.process_recent)
            except Exception as e:
                logger.error(f"Error in batch processing call: {str(e)}", exc_info=True)
            finally:
                logger.info("Batch processing finished or errored. Disconnecting.")
                if client.is_connected(): await client.disconnect()
                return # Exit after batch processing
        
        logger.info(f"Continuous mode: Listening for new posts from {SRC_CHANNEL}")
        logger.info(f"Translation style: {TRANSLATION_STYLE}, Generate images: {GENERATE_IMAGES}")
        await setup_event_handlers(client)
        
        ping_task = asyncio.create_task(ping_server(client))
        
        logger.info("Starting main event loop (run_until_disconnected)")
        await client.run_until_disconnected()

    except Exception as e:
        logger.error(f"Fatal error in run_bot: {str(e)}", exc_info=True)
    finally:
        logger.info("Bot stopping...")
        if client and client.is_connected():
            try:
                await client.disconnect()
                logger.info("Client disconnected.")
            except Exception as e:
                logger.error(f"Error disconnecting client: {str(e)}")
        if 'ping_task' in locals() and not ping_task.done():
            ping_task.cancel()
            try: await ping_task
            except asyncio.CancelledError: logger.info("Ping task cancelled.")
        logger.info("Bot stopped.")

if __name__ == "__main__":
    # Ensure logs directory exists
    log_dir = Path(__file__).resolve().parent.parent / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Ensure session directory exists if specified in SESSION path
    session_path_str = SESSION
    if '/' in session_path_str or '\\' in session_path_str:
        session_dir = Path(session_path_str).parent
        session_dir.mkdir(parents=True, exist_ok=True)

    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Bot interrupted by user (KeyboardInterrupt).")
    except Exception as e: # Catch-all for errors during asyncio.run() or if run_bot itself fails spectacularly
        logger.critical(f"Unhandled exception at top level: {str(e)}", exc_info=True)
    finally:
        logging.shutdown() # Ensure all logs are flushed 