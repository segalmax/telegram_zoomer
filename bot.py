import os
import asyncio
import logging
import time
import sys
from telethon import TelegramClient, events
import openai
from dotenv import load_dotenv
from translator import get_openai_client, translate_text
from image_generator import generate_image_for_post, process_multiple_posts
from telethon.errors import SessionPasswordNeededError

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()] # Keep FileHandler removed for now
)
logger = logging.getLogger(__name__)

# Configuration from environment variables
API_ID = int(os.getenv('TG_API_ID'))
API_HASH = os.getenv('TG_API_HASH')
OPENAI_KEY = os.getenv('OPENAI_API_KEY')
SESSION = os.getenv('TG_SESSION', 'nyt_to_zoom')
SRC_CHANNEL = os.getenv('SRC_CHANNEL')
DST_CHANNEL = os.getenv('DST_CHANNEL')
TRANSLATION_STYLE = os.getenv('TRANSLATION_STYLE', 'both')
GENERATE_IMAGES = os.getenv('GENERATE_IMAGES', 'true').lower() == 'true'

# Initialize OpenAI client
client = get_openai_client(OPENAI_KEY)

# Determine if running in Docker
IN_DOCKER = os.path.exists("/.dockerenv")

# Determine session path
session_dir = "/app/session" if IN_DOCKER else "."
session_path = os.path.join(session_dir, SESSION)

# Create Telegram client with the appropriate session path
tg_client = TelegramClient(session_path, API_ID, API_HASH)

async def translate_and_post(txt, message_id=None):
    """Translate text and post to destination channel with optional image"""
    try:
        start_time = time.time()
        logger.info(f"Starting translation and posting for message ID: {message_id}")
        
        image_data = None
        image_url = None
        
        if GENERATE_IMAGES:
            # Generate image based on post content
            logger.info("Generating image for post...")
            result = await generate_image_for_post(client, txt)
            
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
        
        if TRANSLATION_STYLE == 'both':
            # Translate both styles and post both
            logger.info("Translating in LEFT style...")
            translation_start = time.time()
            left = await translate_text(client, txt, 'left')
            logger.info(f"LEFT translation completed in {time.time() - translation_start:.2f} seconds")
            logger.info(f"LEFT translation snippet: {left[:100]}...")
            
            # Post header, image (if available), and translation
            logger.info("Posting LEFT translation to destination channel...")
            await tg_client.send_message(DST_CHANNEL, "🟢 LEFT-ZOOMER VERSION:")
            
            if image_data:
                # Post with image data
                logger.info("Posting with image data...")
                await tg_client.send_file(DST_CHANNEL, image_data, caption=left[:1024])
                logger.info("LEFT translation with image posted successfully")
            elif image_url:
                # Post left translation with the image URL
                logger.info("Posting with image URL...")
                left_with_url = f"{left}\n\n🖼️ {image_url}"
                await tg_client.send_message(DST_CHANNEL, left_with_url)
                logger.info("LEFT translation with image URL posted successfully")
            else:
                # Post only text
                logger.info("Posting text only...")
                await tg_client.send_message(DST_CHANNEL, left)
                logger.info("LEFT translation (text only) posted successfully")
            
            logger.info("Posted left-leaning version")
            
            logger.info("Translating in RIGHT style...")
            translation_start = time.time()
            right = await translate_text(client, txt, 'right')
            logger.info(f"RIGHT translation completed in {time.time() - translation_start:.2f} seconds")
            logger.info(f"RIGHT translation snippet: {right[:100]}...")
            
            # Post header and translation (reuse image from first post)
            logger.info("Posting RIGHT translation to destination channel...")
            await tg_client.send_message(DST_CHANNEL, "🔴 RIGHT-BIDLO VERSION:")
            await tg_client.send_message(DST_CHANNEL, right)
            logger.info("RIGHT translation posted successfully")
            logger.info("Posted right-wing version")
        else:
            # Translate in configured style only
            style = TRANSLATION_STYLE
            logger.info(f"Translating in {style.upper()} style...")
            translation_start = time.time()
            zoomer = await translate_text(client, txt, style)
            logger.info(f"{style.upper()} translation completed in {time.time() - translation_start:.2f} seconds")
            logger.info(f"Translation snippet: {zoomer[:100]}...")
            
            header = "🟢 LEFT-ZOOMER VERSION:" if style == 'left' else "🔴 RIGHT-BIDLO VERSION:"
            await tg_client.send_message(DST_CHANNEL, header)
            
            if image_data:
                # Post with image data
                logger.info("Posting with image data...")
                await tg_client.send_file(DST_CHANNEL, image_data, caption=zoomer[:1024])
                logger.info("Translation with image posted successfully")
            elif image_url:
                # Post with image URL
                logger.info("Posting with image URL...")
                zoomer_with_url = f"{zoomer}\n\n🖼️ {image_url}"
                await tg_client.send_message(DST_CHANNEL, zoomer_with_url)
                logger.info("Translation with image URL posted successfully")
            else:
                # Post only text
                logger.info("Posting text only...")
                await tg_client.send_message(DST_CHANNEL, zoomer)
                logger.info("Translation (text only) posted successfully")
            
            logger.info("Message successfully posted to destination channel")
        
        processing_time = time.time() - start_time
        logger.info(f"Total processing time for message: {processing_time:.2f} seconds")
        return True
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}", exc_info=True)
        return False

@tg_client.on(events.NewMessage(chats=SRC_CHANNEL))
async def handle_new_message(event):
    """Process new messages from the source channel"""
    try:
        txt = event.message.message
        if not txt:
            return

        logger.info(f"Processing message: {txt[:50]}...")
        await translate_and_post(txt, event.message.id)
        
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}", exc_info=True)

async def process_recent_posts(limit=10, timeout=300):
    """Process N most recent posts from the source channel with timeout"""
    try:
        logger.info(f"Begin processing {limit} most recent posts from channel '{SRC_CHANNEL}'")
        
        # Set a timeout for the entire operation
        start_time = time.time()
        logger.info(f"Setting overall timeout of {timeout} seconds")
        
        # Verify channel exists and is accessible
        logger.info(f"Verifying channel access to '{SRC_CHANNEL}'...")
        try:
            entity = await tg_client.get_entity(SRC_CHANNEL)
            logger.info(f"Successfully resolved channel entity: {entity.id} - {getattr(entity, 'title', 'No title')}")
        except Exception as e:
            logger.error(f"Error accessing channel '{SRC_CHANNEL}': {str(e)}", exc_info=True)
            logger.info("Please verify that SRC_CHANNEL is correct and the bot has access to it")
            return
        
        # Get messages with a timeout
        logger.info(f"Fetching messages from '{SRC_CHANNEL}'...")
        fetch_start = time.time()
        
        # Use a smaller inner timeout for message retrieval
        fetch_timeout = min(60, timeout / 2)  # 60 seconds or half the total timeout
        
        try:
            # Set up a task with timeout
            fetch_task = asyncio.create_task(process_multiple_posts(tg_client, SRC_CHANNEL, limit))
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
        for idx, message in enumerate(reversed(messages)):
            # Check if timeout is approaching
            if time.time() - start_time > timeout * 0.9:
                logger.warning(f"Approaching timeout after processing {processed_count} messages. Stopping.")
                break
                
            txt = message.text
            if not txt:
                logger.info(f"Skipping message {idx+1} (no text content)")
                continue
                
            logger.info(f"Processing message {idx+1}/{len(messages)}: {txt[:50]}...")
            start_msg_time = time.time()
            
            success = await translate_and_post(txt, message.id)
            
            if success:
                processed_count += 1
                logger.info(f"Successfully processed message {idx+1} in {time.time() - start_msg_time:.2f} seconds")
            else:
                logger.error(f"Failed to process message {idx+1}")
            
            # Add a small delay between posts to avoid rate limiting
            logger.info("Waiting 5 seconds before next message...")
            await asyncio.sleep(5)
            
        elapsed = time.time() - start_time
        logger.info(f"Finished processing {processed_count} of {len(messages)} posts in {elapsed:.2f} seconds")
        
    except Exception as e:
        logger.error(f"Error processing recent posts: {str(e)}", exc_info=True)

async def main():
    """Main entry point"""
    logger.info("Starting Telegram Zoomer bot")
    logger.info(f"Python version: {sys.version}")
    
    # Verify all required env vars are present
    required_vars = ['TG_API_ID', 'TG_API_HASH', 'OPENAI_API_KEY', 'SRC_CHANNEL', 'DST_CHANNEL']
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        return
    
    try:
        # Use non-interactive start in Docker environment
        if IN_DOCKER:
            try:
                # If session file doesn't exist in Docker, we'll need to exit
                if not os.path.exists(session_path + ".session"):
                    logger.error("Session file not found in Docker environment.")
                    logger.error("Please run the bot locally first to create a session file.")
                    logger.error("Then copy it to the Docker volume or bind mount.")
                    return
                
                # Start without user input
                logger.info("Starting client in non-interactive Docker mode (await tg_client.start())...")
                start_call_time = time.time()
                await tg_client.start()
                logger.info(f"await tg_client.start() completed in Docker mode after {time.time() - start_call_time:.2f} seconds")
            except Exception as e:
                logger.error(f"Failed to start in Docker: {str(e)}", exc_info=True)
                return
        else:
            # Interactive start for local development using manual login flow
            logger.info("Starting client in interactive local mode (manual connect)...")
            await tg_client.connect()
            if not await tg_client.is_user_authorized():
                # Prompt for phone and code if not authorized
                phone = "+972509909987"
                logger.info(f"Sending login code to {phone}...")
                await tg_client.send_code_request(phone)
                code = input("Enter the login code you received on Telegram: ")
                try:
                    await tg_client.sign_in(phone, code)
                except SessionPasswordNeededError:
                    password = input("Two-factor password: ")
                    await tg_client.sign_in(password=password)
            logger.info("Client authorized and connected (manual flow)")
        
        logger.info("Client successfully started, proceeding with execution logic...")
        
        # Check for --process-recent flag in command line args
        if "--process-recent" in sys.argv:
            # Get number of posts to process (default 10)
            try:
                idx = sys.argv.index("--process-recent")
                if idx + 1 < len(sys.argv) and sys.argv[idx + 1].isdigit():
                    limit = int(sys.argv[idx + 1])
                else:
                    limit = 10
                    
                logger.info(f"Running in batch mode to process {limit} recent posts")
            except (ValueError, IndexError):
                limit = 10
                logger.info(f"Running in batch mode with default limit of {limit} posts")
                
            await process_recent_posts(limit)
            logger.info("Batch processing completed, exiting")
            # Exit after processing
            return
            
        logger.info(f"Listening for new posts from {SRC_CHANNEL}")
        logger.info(f"Translation style: {TRANSLATION_STYLE}")
        logger.info(f"Generate images: {GENERATE_IMAGES}")
        await tg_client.run_until_disconnected()
    except Exception as e:
        logger.error(f"Critical error: {str(e)}", exc_info=True)
    finally:
        logger.info("Bot stopped")

if __name__ == "__main__":
    asyncio.run(main()) 