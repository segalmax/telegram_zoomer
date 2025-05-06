import os
import asyncio
import logging
import time
import sys
import uuid
import re
from telethon import TelegramClient, events
from telethon.network import ConnectionTcpAbridged
import openai
from dotenv import load_dotenv
from translator import get_openai_client, translate_text
from image_generator import generate_image_for_post

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration from environment variables
API_ID = int(os.getenv('TG_API_ID'))
API_HASH = os.getenv('TG_API_HASH')
OPENAI_KEY = os.getenv('OPENAI_API_KEY')
TG_PHONE = os.getenv('TG_PHONE')
SESSION = os.getenv('TG_SESSION', 'new_session')  # Use the authenticated session
SRC_CHANNEL = os.getenv('SRC_CHANNEL')
DST_CHANNEL = os.getenv('DST_CHANNEL')
TRANSLATION_STYLE = os.getenv('TRANSLATION_STYLE', 'both')
GENERATE_IMAGES = os.getenv('GENERATE_IMAGES', 'true').lower() == 'true'
USE_STABILITY_AI = os.getenv('USE_STABILITY_AI', 'false').lower() == 'true'

# Initialize OpenAI client
openai_client = get_openai_client(OPENAI_KEY)

def extract_nytimes_link(text):
    """Extract NYTimes link from the post text"""
    # Pattern to match NYTimes URLs
    nyt_patterns = [
        r'https?://(?:www\.)?nytimes\.com/\S+',
        r'https?://(?:www\.)?nyti\.ms/\S+'
    ]
    
    for pattern in nyt_patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    
    return None

async def translate_and_post(client, txt, message_id=None, original_url=None, destination_channel=None):
    """Translate text and post to destination channel with optional image"""
    try:
        start_time = time.time()
        logger.info(f"Starting translation and posting for message ID: {message_id}")
        
        # Use provided destination channel or default to environment variable
        dst_channel = destination_channel or DST_CHANNEL
        logger.info(f"Using destination channel: {dst_channel}")
        
        # Extract NYTimes link if not provided
        if not original_url:
            original_url = extract_nytimes_link(txt)
            if original_url:
                logger.info(f"Extracted NYTimes URL: {original_url}")
            else:
                logger.info("No NYTimes URL found in the message")
        
        image_data = None
        image_url = None
        
        if GENERATE_IMAGES:
            # Generate image based on post content
            logger.info("Generating image for post...")
            result = await generate_image_for_post(openai_client, txt)
            
            # Handle different return types (BytesIO or URL string)
            if result:
                if isinstance(result, str):
                    # It's a URL
                    image_url = result
                    logger.info("Using image URL instead of direct upload")
                else:
                    # It's BytesIO data
                    image_data = result
                    logger.info("Image data received successfully")
            else:
                logger.warning("No image result was returned")
        
        # Create source attribution footer
        source_footer = ""
        if original_url:
            source_footer = f"\n\n🔗 Оригинал: {original_url}"
            logger.info("Added source attribution footer with NYTimes link")
        
        if TRANSLATION_STYLE == 'both':
            # Translate both styles and post both
            logger.info("Translating in LEFT style...")
            translation_start = time.time()
            left = await translate_text(openai_client, txt, 'left')
            logger.info(f"LEFT translation completed in {time.time() - translation_start:.2f} seconds")
            logger.info(f"LEFT translation snippet: {left[:100]}...")
            
            # Add source footer to left translation
            left_with_source = left + source_footer if source_footer else left
            
            # Post header, image (if available), and translation
            logger.info("Posting LEFT translation to destination channel...")
            await client.send_message(dst_channel, "🟢 LEFT-ZOOMER VERSION:")
            
            if image_data:
                # Post with image data - caption limited to 1024 chars
                logger.info("Posting with image data...")
                caption = left[:1024 - len(source_footer)] + source_footer if source_footer else left[:1024]
                await client.send_file(dst_channel, image_data, caption=caption)
                
                # If caption was truncated due to length, send the rest as a separate message
                if len(left) > 1024 - len(source_footer):
                    await client.send_message(dst_channel, left[1024 - len(source_footer):] + source_footer)
                
                logger.info("LEFT translation with image posted successfully")
            elif image_url:
                # Post left translation with the image URL
                logger.info("Posting with image URL...")
                left_with_url = f"{left}\n\n🖼️ {image_url}{source_footer}"
                await client.send_message(dst_channel, left_with_url)
                logger.info("LEFT translation with image URL posted successfully")
            else:
                # Post only text
                logger.info("Posting text only...")
                await client.send_message(dst_channel, left_with_source)
                logger.info("LEFT translation (text only) posted successfully")
            
            logger.info("Posted left-leaning version")
            
            logger.info("Translating in RIGHT style...")
            translation_start = time.time()
            right = await translate_text(openai_client, txt, 'right')
            logger.info(f"RIGHT translation completed in {time.time() - translation_start:.2f} seconds")
            logger.info(f"RIGHT translation snippet: {right[:100]}...")
            
            # Add source footer to right translation
            right_with_source = right + source_footer if source_footer else right
            
            # Post header and translation (reuse image from first post)
            logger.info("Posting RIGHT translation to destination channel...")
            await client.send_message(dst_channel, "🔴 RIGHT-BIDLO VERSION:")
            await client.send_message(dst_channel, right_with_source)
            logger.info("RIGHT translation posted successfully")
            logger.info("Posted right-wing version")
        else:
            # Translate in configured style only
            style = TRANSLATION_STYLE
            logger.info(f"Translating in {style.upper()} style...")
            translation_start = time.time()
            zoomer = await translate_text(openai_client, txt, style)
            logger.info(f"{style.upper()} translation completed in {time.time() - translation_start:.2f} seconds")
            logger.info(f"Translation snippet: {zoomer[:100]}...")
            
            # Add source footer
            zoomer_with_source = zoomer + source_footer if source_footer else zoomer
            
            header = "🟢 LEFT-ZOOMER VERSION:" if style == 'left' else "🔴 RIGHT-BIDLO VERSION:"
            await client.send_message(dst_channel, header)
            
            if image_data:
                # Post with image data - caption limited to 1024 chars
                logger.info("Posting with image data...")
                caption = zoomer[:1024 - len(source_footer)] + source_footer if source_footer else zoomer[:1024]
                await client.send_file(dst_channel, image_data, caption=caption)
                
                # If caption was truncated due to length, send the rest as a separate message
                if len(zoomer) > 1024 - len(source_footer):
                    await client.send_message(dst_channel, zoomer[1024 - len(source_footer):] + source_footer)
                
                logger.info("Translation with image posted successfully")
            elif image_url:
                # Post with image URL
                logger.info("Posting with image URL...")
                zoomer_with_url = f"{zoomer}\n\n🖼️ {image_url}{source_footer}"
                await client.send_message(dst_channel, zoomer_with_url)
                logger.info("Translation with image URL posted successfully")
            else:
                # Post only text
                logger.info("Posting text only...")
                await client.send_message(dst_channel, zoomer_with_source)
                logger.info("Translation (text only) posted successfully")
            
            logger.info("Message successfully posted to destination channel")
        
        processing_time = time.time() - start_time
        logger.info(f"Total processing time for message: {processing_time:.2f} seconds")
        return True
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}", exc_info=True)
        return False

async def setup_event_handlers(client):
    @client.on(events.NewMessage(chats=SRC_CHANNEL))
    async def handle_new_message(event):
        """Process new messages from the source channel"""
        try:
            txt = event.message.message
            if not txt:
                return

            logger.info(f"Processing message: {txt[:50]}...")
            
            # Extract URL from message entities if available
            original_url = None
            if event.message.entities:
                for entity in event.message.entities:
                    if hasattr(entity, 'url'):
                        url = entity.url
                        if 'nytimes.com' in url or 'nyti.ms' in url:
                            original_url = url
                            logger.info(f"Found NYTimes URL in message entities: {original_url}")
                            break
            
            await translate_and_post(client, txt, event.message.id, original_url)
            
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True)

async def process_recent_posts(client, limit=10, timeout=300):
    """Process N most recent posts from the source channel with timeout"""
    try:
        logger.info(f"Begin processing {limit} most recent posts from channel '{SRC_CHANNEL}'")
        
        # Set a timeout for the entire operation
        start_time = time.time()
        logger.info(f"Setting overall timeout of {timeout} seconds")
        
        # Get messages with a timeout
        logger.info(f"Fetching messages from '{SRC_CHANNEL}'...")
        fetch_start = time.time()
        
        # Use a smaller inner timeout for message retrieval
        fetch_timeout = min(60, timeout / 2)  # 60 seconds or half the total timeout
        
        try:
            # Set up a task with timeout
            fetch_task = asyncio.create_task(client.get_messages(SRC_CHANNEL, limit=limit))
            messages = await asyncio.wait_for(fetch_task, timeout=fetch_timeout)
            fetch_time = time.time() - fetch_start
            logger.info(f"Fetched {len(messages)} messages in {fetch_time:.2f} seconds")
        except asyncio.TimeoutError:
            logger.error(f"Timed out after {fetch_timeout} seconds while fetching messages from '{SRC_CHANNEL}'")
            logger.info("Try using a different channel or check network connectivity")
            return
        
        if not messages:
            logger.warning(f"No messages found in channel '{SRC_CHANNEL}'")
            return
        
        logger.info(f"Retrieved {len(messages)} messages:")
        for idx, msg in enumerate(messages):
            if msg.text:
                logger.info(f"  Message {idx+1}: {msg.id} - {msg.text[:50]}...")
            else:
                logger.info(f"  Message {idx+1}: {msg.id} - No text content")
        
        # Process messages in reverse order (oldest first)
        logger.info(f"Processing messages in reverse order (oldest first)...")
        
        processed_count = 0
        remaining_time = timeout - (time.time() - start_time)
        
        # Estimate time per message and adjust batch size if needed
        estimated_time_per_msg = remaining_time / limit  # Estimate based on total available time
        logger.info(f"Estimated time per message: {estimated_time_per_msg:.2f} seconds")
        
        # If we're running out of time, process fewer messages
        if estimated_time_per_msg < 10:  # If less than 10 seconds per message
            adjusted_limit = max(1, int(remaining_time / 30))  # Allow at least 30s per message
            if adjusted_limit < limit:
                logger.warning(f"Adjusting batch size from {limit} to {adjusted_limit} messages due to time constraints")
                messages = messages[:adjusted_limit]
        
        for msg in reversed(messages):
            # Skip messages without text
            if not msg.text:
                logger.info(f"Skipping message {msg.id} - No text content")
                continue
                
            # Check overall timeout
            if time.time() - start_time > timeout - 30:  # Reserve 30s for cleanup
                logger.warning(f"Approaching timeout limit, stopping after processing {processed_count} messages")
                break
                
            logger.info(f"Processing message {msg.id}: {msg.text[:50]}...")
            
            # Process with individual timeout
            try:
                processing_timeout = min(180, (timeout - (time.time() - start_time)) / 2)
                logger.info(f"Setting per-message timeout of {processing_timeout:.2f} seconds")
                
                process_task = asyncio.create_task(
                    translate_and_post(
                        client,
                        msg.text,
                        msg.id
                    )
                )
                success = await asyncio.wait_for(process_task, timeout=processing_timeout)
                
                if success:
                    processed_count += 1
                    logger.info(f"Successfully processed message {msg.id} ({processed_count}/{len(messages)})")
                else:
                    logger.warning(f"Failed to process message {msg.id}")
            except asyncio.TimeoutError:
                logger.error(f"Timed out processing message {msg.id} after {processing_timeout:.2f} seconds")
            except Exception as e:
                logger.error(f"Error processing message {msg.id}: {str(e)}", exc_info=True)
            
            # Brief pause between messages to avoid rate limits
            await asyncio.sleep(1)
        
        logger.info(f"Batch processing completed. Processed {processed_count}/{len(messages)} messages")
        return processed_count
    except Exception as e:
        logger.error(f"Error in batch processing: {str(e)}", exc_info=True)
        return 0

async def ping_server(client):
    """Periodically ping server to maintain connection"""
    logger.info("Starting background ping process...")
    while True:
        try:
            if not client.is_connected():
                logger.warning("Connection lost, attempting to reconnect...")
                await client.connect()
                
            # Perform a simple operation to check connection
            me = await client.get_me()
            if me:
                logger.info(f"Ping successful - connected as {me.first_name}")
            else:
                logger.warning("Ping failed - no user info returned")
                
            # Check if client is receiving updates
            if not client.is_connected():
                logger.warning("Client disconnected during ping")
        except Exception as e:
            logger.error(f"Error during ping: {str(e)}")
            try:
                logger.info("Attempting to reconnect...")
                await client.disconnect()
                await asyncio.sleep(5)  # Wait 5 seconds before reconnecting
                await client.connect()
                # Check if reconnection was successful
                if await client.is_user_authorized():
                    logger.info("Successfully reconnected and authorized")
                else:
                    logger.error("Reconnection failed - not authorized")
            except Exception as reconnect_error:
                logger.error(f"Reconnection attempt failed: {str(reconnect_error)}")
        
        # Wait 5 minutes before next ping
        await asyncio.sleep(300)

async def run_bot():
    """Main function to run the bot"""
    logger.info("Starting Telegram Zoomer bot")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Using session file: {SESSION}")
    
    client = None
    try:
        # Create client with ConnectionTcpAbridged (more reliable than default)
        logger.info("Connecting to Telegram...")
        client = TelegramClient(
            SESSION, 
            API_ID, 
            API_HASH,
            connection=ConnectionTcpAbridged,
            device_model="Macbook",
            system_version="macOS 14",
            app_version="Telegram Zoomer Bot 1.0",
            receive_updates=True,
            auto_reconnect=True,
            retry_delay=5,
            connection_retries=10
        )
        
        # Connect with timeout
        try:
            connect_task = asyncio.create_task(client.connect())
            await asyncio.wait_for(connect_task, timeout=30)
            logger.info("Connected successfully")
        except asyncio.TimeoutError:
            logger.error("Timed out while connecting to Telegram")
            if client and client.is_connected():
                await client.disconnect()
            return
        
        # Check if already authorized - we should be using an authenticated session
        if not await client.is_user_authorized():
            logger.error("Session file is not authorized. Please run scripts/complete_auth.py first.")
            if client and client.is_connected():
                await client.disconnect()
            return
        
        # We're authenticated, start the client properly
        logger.info("Already authorized") 
        
        # Start client (this ensures proper connection)
        try:
            start_task = asyncio.create_task(client.start())
            await asyncio.wait_for(start_task, timeout=30)
            logger.info("Successfully authorized - ready to process messages")
        except asyncio.TimeoutError:
            logger.error("Timed out while starting client")
            if client and client.is_connected():
                await client.disconnect()
            return
        except Exception as e:
            logger.error(f"Error starting client: {str(e)}")
            if client and client.is_connected():
                await client.disconnect()
            return
                
        # Check command line arguments
        import argparse
        parser = argparse.ArgumentParser(description='Telegram NYT-to-Zoomer Bot')
        parser.add_argument('--process-recent', type=int, help='Process N most recent posts')
        args = parser.parse_args()
        
        if args.process_recent:
            # Process recent posts in batch mode
            try:
                await process_recent_posts(client, limit=args.process_recent)
                logger.info("Batch processing completed")
            except Exception as e:
                logger.error(f"Error in batch processing: {str(e)}")
            finally:
                if client and client.is_connected():
                    await client.disconnect()
                return
        
        # Set up event handlers for continuous mode
        logger.info(f"Listening for new posts from {SRC_CHANNEL}")
        logger.info(f"Translation style: {TRANSLATION_STYLE}")
        logger.info(f"Generate images: {GENERATE_IMAGES}")
        
        # Register the event handler directly
        await setup_event_handlers(client)
        
        # Verify event handler is listening
        logger.info("Verifying event handler registration...")
        registered_handlers = client.list_event_handlers()
        if registered_handlers:
            logger.info(f"Registered {len(registered_handlers)} event handlers")
            for handler in registered_handlers:
                if isinstance(handler[0], events.NewMessage.Event):
                    logger.info(f"Found NewMessage handler for chats: {handler[0].chats}")
        else:
            logger.warning("No event handlers registered! Bot won't respond to new messages.")
        
        # Start ping task in background
        ping_task = asyncio.create_task(ping_server(client))
        
        # Run the client until disconnected
        try:
            logger.info("Starting main event loop")
            await client.run_until_disconnected()
        except Exception as e:
            logger.error(f"Error in main event loop: {str(e)}")
        finally:
            # Cancel ping task
            if not ping_task.done():
                ping_task.cancel()
                try:
                    await ping_task
                except asyncio.CancelledError:
                    pass
    except Exception as e:
        logger.error(f"Bot error: {str(e)}", exc_info=True)
    finally:
        logger.info("Bot stopped")
        # Ensure client is properly disconnected to avoid DB locks
        if client and client.is_connected():
            try:
                await client.disconnect()
                logger.info("Client disconnected")
            except Exception as e:
                logger.error(f"Error disconnecting client: {str(e)}")

if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True) 