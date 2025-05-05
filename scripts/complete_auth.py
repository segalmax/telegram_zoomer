import os
import asyncio
import logging
from telethon import TelegramClient
from telethon.network import ConnectionTcpAbridged
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration from environment
API_ID = int(os.getenv('TG_API_ID'))
API_HASH = os.getenv('TG_API_HASH')
PHONE = os.getenv('TG_PHONE')

# The main session file to use for the bot
SESSION = "new_session"

async def complete_authentication():
    """Complete the authentication process by signing in with a code"""
    
    # Create client with the most reliable connection type
    client = TelegramClient(
        SESSION, 
        API_ID, 
        API_HASH,
        connection=ConnectionTcpAbridged,
        connection_retries=1,
        retry_delay=1,
        timeout=15,
        use_ipv6=False
    )
    
    try:
        # Connect with timeout
        logger.info("Connecting to Telegram...")
        connect_task = asyncio.create_task(client.connect())
        await asyncio.wait_for(connect_task, timeout=30)
        logger.info("Connected successfully")
        
        # Check if already authorized
        if await client.is_user_authorized():
            logger.info("Already authorized, no need to enter code")
            me = await client.get_me()
            logger.info(f"Logged in as: {me.first_name} {getattr(me, 'last_name', '')}")
            return True
            
        # Request code if not authorized
        logger.info(f"Sending code request to {PHONE}")
        await client.send_code_request(PHONE)
        
        # Try to sign in with the code (with multiple attempts)
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                # Get the verification code from the user
                code = input(f"Attempt {attempt}/{max_attempts}: Enter the Telegram code you received: ")
                if not code.strip():
                    logger.warning("Empty code entered, try again")
                    continue
                
                logger.info(f"Signing in with code: {code}")
                await client.sign_in(PHONE, code)
                
                # Successfully signed in
                me = await client.get_me()
                logger.info(f"Successfully signed in as: {me.first_name} {getattr(me, 'last_name', '')}")
                logger.info(f"Auth completed! Session saved to {SESSION}.session")
                logger.info("You can now run the bot normally.")
                return True
                
            except PhoneCodeInvalidError:
                if attempt < max_attempts:
                    logger.warning("Invalid code entered. Please try again.")
                else:
                    logger.error("Maximum attempts reached with invalid codes.")
                    return False
                    
            except SessionPasswordNeededError:
                logger.info("Two-factor authentication required")
                
                # Ask for 2FA password
                password = input("Enter your two-factor authentication password: ")
                
                try:
                    await client.sign_in(password=password)
                    me = await client.get_me()
                    logger.info(f"Successfully signed in with 2FA as: {me.first_name} {getattr(me, 'last_name', '')}")
                    logger.info(f"Auth completed! Session saved to {SESSION}.session")
                    return True
                except Exception as e:
                    logger.error(f"Failed to sign in with 2FA: {str(e)}")
                    return False
                    
            except Exception as e:
                logger.error(f"Error during sign in attempt {attempt}: {str(e)}")
                if attempt >= max_attempts:
                    return False
                logger.info("Retrying with a new code...")
            
    except Exception as e:
        logger.error(f"Error during authentication: {str(e)}")
        return False
        
    finally:
        if client and client.is_connected():
            await client.disconnect()
            logger.info("Disconnected")

if __name__ == "__main__":
    logger.info("Starting authentication process...")
    asyncio.run(complete_authentication()) 