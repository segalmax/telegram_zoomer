from telethon import TelegramClient
from telethon.sessions import StringSession
import os, base64, gzip, textwrap

print("Creating Heroku session...")
api_id = int(os.environ['TG_API_ID'])
api_hash = os.environ['TG_API_HASH']
phone = os.environ['TG_PHONE']

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print("Starting client and authenticating...")
    client.start(phone=phone)
    print("Getting session string...")
    sess = client.session.save()
    compressed = base64.b64encode(gzip.compress(sess.encode())).decode()
    print('\n' + '-'*72)
    print('Add this to Heroku config vars as TG_COMPRESSED_SESSION_STRING:')
    print(textwrap.fill(compressed, 76))
    print('-'*72)
    print("Session creation complete!") 