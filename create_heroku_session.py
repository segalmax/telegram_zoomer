import asyncio
from telethon import TelegramClient
import os
from dotenv import load_dotenv
from pathlib import Path

project_root = Path(__file__).resolve().parent # Assuming create_heroku_session.py is in the root
load_dotenv(dotenv_path=project_root / 'app_settings.env', override=True)
load_dotenv(dotenv_path=project_root / '.env', override=False) # For API_ID, API_HASH, TG_PHONE

API_ID = os.getenv('TG_API_ID')
API_HASH = os.getenv('TG_API_HASH')
PHONE = os.getenv('TG_PHONE')
NEW_SESSION_NAME = 'heroku_bot_session' # This is the new session name

async def main():
    session_path = f"session/{NEW_SESSION_NAME}"
    print(f"Attempting to create and authorize session: {session_path}.session")
    
    # Ensure the 'session' directory exists
    if not os.path.exists('session'):
        os.makedirs('session')
        print("Created 'session' directory.")

    client = TelegramClient(session_path, API_ID, API_HASH)
    
    print("Connecting to Telegram...")
    await client.connect()
    print("Connected.")

    if not await client.is_user_authorized():
        print(f"Session is not authorized. Please prepare to authenticate for: {PHONE}")
        await client.send_code_request(PHONE)
        print("Code request sent.")
        code = input('Please enter the code you received: ')
        try:
            await client.sign_in(PHONE, code)
            print("Signed in successfully!")
        except Exception as e:
            print(f"Failed to sign in: {e}")
            print("If you have 2FA enabled, you might need to provide your password.")
            try:
                password = input("Please enter your Telegram password (2FA): ")
                await client.sign_in(password=password)
                print("Signed in successfully with 2FA password!")
            except Exception as e_pw:
                print(f"Failed to sign in with 2FA password: {e_pw}")
                await client.disconnect()
                return
    else:
        print("Session is already authorized.")
    
    me = await client.get_me()
    if me:
        print(f"Successfully signed in as: {me.first_name} (ID: {me.id})")
    else:
        print("Could not get user details, but session should be created.")
        
    await client.disconnect()
    print(f"Client disconnected. Session file {session_path}.session should now be created/updated.")

if __name__ == '__main__':
    asyncio.run(main()) 