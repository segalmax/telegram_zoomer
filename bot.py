import os
import asyncio
import logging
from telethon import TelegramClient, events
import openai
from dotenv import load_dotenv
from translator import get_openai_client, translate_text
from image_generator import generate_image_for_post, process_multiple_posts

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler("bot.log")]
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
        image_data = None
        if GENERATE_IMAGES:
            # Generate image based on post content
            logger.info("Generating image for post...")
            image_data = await generate_image_for_post(client, txt)
        
        if TRANSLATION_STYLE == 'both':
            # Translate both styles and post both
            logger.info("Translating in LEFT style...")
            left = await translate_text(client, txt, 'left')
            logger.info(f"LEFT translation snippet: {left[:100]}...")
            
            # Post header, image (if available), and translation
            await tg_client.send_message(DST_CHANNEL, "🟢 LEFT-ZOOMER VERSION:")
            if image_data:
                await tg_client.send_file(DST_CHANNEL, image_data, caption=left[:1024])
            else:
                await tg_client.send_message(DST_CHANNEL, left)
            logger.info("Posted left-leaning version")
            
            logger.info("Translating in RIGHT style...")
            right = await translate_text(client, txt, 'right')
            logger.info(f"RIGHT translation snippet: {right[:100]}...")
            
            # Post header and translation (reuse image from first post)
            await tg_client.send_message(DST_CHANNEL, "🔴 RIGHT-BIDLO VERSION:")
            await tg_client.send_message(DST_CHANNEL, right)
            logger.info("Posted right-wing version")
        else:
            # Translate in configured style only
            style = TRANSLATION_STYLE
            logger.info(f"Translating in {style.upper()} style...")
            zoomer = await translate_text(client, txt, style)
            logger.info(f"Translation snippet: {zoomer[:100]}...")
            
            header = "🟢 LEFT-ZOOMER VERSION:" if style == 'left' else "🔴 RIGHT-BIDLO VERSION:"
            await tg_client.send_message(DST_CHANNEL, header)
            
            if image_data:
                await tg_client.send_file(DST_CHANNEL, image_data, caption=zoomer[:1024])
            else:
                await tg_client.send_message(DST_CHANNEL, zoomer)
            logger.info("Message successfully posted to destination channel")
        
        return True
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
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
        logger.error(f"Error processing message: {str(e)}")

async def process_recent_posts(limit=10):
    """Process N most recent posts from the source channel"""
    try:
        logger.info(f"Processing {limit} most recent posts from {SRC_CHANNEL}")
        messages = await process_multiple_posts(tg_client, SRC_CHANNEL, limit)
        
        if not messages:
            logger.warning("No messages found to process")
            return
        
        # Process messages in reverse order (oldest first)
        for message in reversed(messages):
            txt = message.text
            if not txt:
                continue
                
            logger.info(f"Processing historical message: {txt[:50]}...")
            await translate_and_post(txt, message.id)
            # Add a small delay between posts to avoid rate limiting
            await asyncio.sleep(5)
            
        logger.info(f"Finished processing {len(messages)} historical posts")
    except Exception as e:
        logger.error(f"Error processing recent posts: {str(e)}")

async def main():
    """Main entry point"""
    logger.info("Starting Telegram Zoomer bot")
    
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
                await tg_client.start()
            except Exception as e:
                logger.error(f"Failed to start in Docker: {str(e)}")
                return
        else:
            # Interactive start for local development
            await tg_client.start()
        
        # Check for --process-recent flag in command line args
        import sys
        if "--process-recent" in sys.argv:
            # Get number of posts to process (default 10)
            try:
                idx = sys.argv.index("--process-recent")
                if idx + 1 < len(sys.argv) and sys.argv[idx + 1].isdigit():
                    limit = int(sys.argv[idx + 1])
                else:
                    limit = 10
            except (ValueError, IndexError):
                limit = 10
                
            await process_recent_posts(limit)
            # Exit after processing
            return
            
        logger.info(f"Listening for new posts from {SRC_CHANNEL}")
        logger.info(f"Translation style: {TRANSLATION_STYLE}")
        logger.info(f"Generate images: {GENERATE_IMAGES}")
        await tg_client.run_until_disconnected()
    except Exception as e:
        logger.error(f"Critical error: {str(e)}")
    finally:
        logger.info("Bot stopped")

if __name__ == "__main__":
    asyncio.run(main()) 