#!/usr/bin/env python3
"""
generate_string_session.py
-------------------------
A tiny helper that walks you through creating a **StringSession** for any
Telegram account (bot or user) and optionally compresses + base-64 encodes it
for easy storage in environment variables.

Usage examples:

1. Raw StringSession (prints to stdout):
   $ python scripts/generate_string_session.py

2. Compressed+base64 (good for env vars like TG_SENDER_COMPRESSED_SESSION_STRING):
   $ python scripts/generate_string_session.py --compress

3. Non-interactive (already know the code; provide via args):
   $ python scripts/generate_string_session.py --phone +1555123456 --code 12345

Environment variables required (or supply via --api-id / --api-hash):
   TG_API_ID, TG_API_HASH
"""

import argparse
import asyncio
import base64
import gzip
import os
import sys
from telethon import TelegramClient
from telethon.sessions import StringSession


async def main():
    parser = argparse.ArgumentParser(description="Generate and optionally compress a Telegram StringSession")
    parser.add_argument("--api-id", type=int, default=os.getenv("TG_API_ID"), help="Telegram API ID (or set TG_API_ID env var)")
    parser.add_argument("--api-hash", default=os.getenv("TG_API_HASH"), help="Telegram API HASH (or set TG_API_HASH env var)")
    parser.add_argument("--phone", help="Phone number or bot token. If omitted you'll be prompted.")
    parser.add_argument("--code", help="Login code (5 digits). If omitted you'll be prompted when Telegram sends it.")
    parser.add_argument("--password", help="2-FA password (if enabled). If omitted you will be prompted.")
    parser.add_argument("--compress", action="store_true", help="Output gzip+base64 string instead of raw session")
    args = parser.parse_args()

    if not args.api_id or not args.api_hash:
        print("Error: API ID / HASH missing. Provide --api-id/--api-hash or set TG_API_ID/TG_API_HASH.")
        sys.exit(1)

    session = StringSession()
    async with TelegramClient(session, args.api_id, args.api_hash) as client:
        phone = args.phone or input("Please enter your phone (or bot token): ")
        if await client.is_user_authorized():
            print("Already authorised – generating session string…")
        else:
            await client.send_code_request(phone)
            code = args.code or input("Enter the code Telegram just sent you: ")
            try:
                await client.sign_in(phone=phone, code=code)
            except Exception as e:
                if "password" in str(e).lower():
                    pwd = args.password or input("Your account has 2-FA enabled. Enter your password: ")
                    await client.sign_in(password=pwd)
                else:
                    raise

        raw_session = client.session.save()
        if args.compress:
            compressed = base64.b64encode(gzip.compress(raw_session.encode())).decode()
            print("\n--- COPY the following into TG_SENDER_COMPRESSED_SESSION_STRING ---\n")
            print(compressed)
        else:
            print("\n--- COPY the following into TG_SENDER_SESSION_STRING ---\n")
            print(raw_session)
        print("\nDone! Paste the value into your .env and re-run your tests.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nAborted by user.") 