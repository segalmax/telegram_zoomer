import os
import asyncio
import logging
from telethon import TelegramClient, events
import openai
from dotenv import load_dotenv
from translator import get_openai_client, translate_text

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

# Initialize OpenAI client
client = get_openai_client(OPENAI_KEY)

# Determine if running in Docker
IN_DOCKER = os.path.exists("/.dockerenv")

# Determine session path
session_dir = "/app/session" if IN_DOCKER else "."
session_path = os.path.join(session_dir, SESSION)

# Create Telegram client with the appropriate session path
tg_client = TelegramClient(session_path, API_ID, API_HASH)

@tg_client.on(events.NewMessage(chats=SRC_CHANNEL))
async def handle_new_message(event):
    """Process new messages from the source channel"""
    try:
        txt = event.message.message
        if not txt:
            return

        logger.info(f"Processing message: {txt[:50]}...")
        
        if TRANSLATION_STYLE == 'both':
            # Translate both styles and post both
            logger.info("Translating in LEFT style...")
            left = await translate_text(client, txt, 'left')
            logger.info(f"LEFT translation snippet: {left[:100]}...")
            
            await tg_client.send_message(DST_CHANNEL, "🟢 LEFT-ZOOMER VERSION:")
            await tg_client.send_message(DST_CHANNEL, left)
            logger.info("Posted left-leaning version")
            
            logger.info("Translating in RIGHT style...")
            right = await translate_text(client, txt, 'right')
            logger.info(f"RIGHT translation snippet: {right[:100]}...")
            
            await tg_client.send_message(DST_CHANNEL, "🔴 RIGHT-BIDLO VERSION:")
            await tg_client.send_message(DST_CHANNEL, right)
            logger.info("Posted right-wing version")
        else:
            # Translate in configured style only
            style = TRANSLATION_STYLE
            logger.info(f"Translating in {style.upper()} style...")
            zoomer = await translate_text(client, txt, style)
            logger.info(f"Translation snippet: {zoomer[:100]}...")
            
            if style == 'left':
                await tg_client.send_message(DST_CHANNEL, "🟢 LEFT-ZOOMER VERSION:")
            elif style == 'right':
                await tg_client.send_message(DST_CHANNEL, "🔴 RIGHT-BIDLO VERSION:")
            
            await tg_client.send_message(DST_CHANNEL, zoomer)
            logger.info("Message successfully posted to destination channel")
        
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")

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
            
        logger.info(f"Listening for new posts from {SRC_CHANNEL}")
        logger.info(f"Translation style: {TRANSLATION_STYLE}")
        await tg_client.run_until_disconnected()
    except Exception as e:
        logger.error(f"Critical error: {str(e)}")
    finally:
        logger.info("Bot stopped")

if __name__ == "__main__":
    asyncio.run(main()) 