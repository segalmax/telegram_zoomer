#!/usr/bin/env python3
"""
Test script that fetches the latest post from source channel,
translates it into two styles (left-leaning zoomer and right-wing bidlo), and posts both.
"""

import os
import asyncio
import logging
from dotenv import load_dotenv
from telethon import TelegramClient
import openai

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration from environment variables
API_ID = int(os.getenv('TG_API_ID'))
API_HASH = os.getenv('TG_API_HASH')
OPENAI_KEY = os.getenv('OPENAI_API_KEY')
SESSION = os.getenv('TG_SESSION', 'nyt_to_zoom')
SRC_CHANNEL = os.getenv('SRC_CHANNEL')
DST_CHANNEL = os.getenv('DST_CHANNEL')

# Initialize OpenAI client
client = openai.OpenAI(api_key=OPENAI_KEY)

def translate_left(text):
    """Translate text to casual, left-leaning Russian zoomer slang"""
    prompt = (
        "You are a razor-sharp Russian Gen Z activist with biting wit. "
        "Rewrite this news entirely in Russian, using edgy, punchy zoomer slang with savage humor—no English allowed, only Russian loanwords with Russian endings. "
        "Include one darkly funny punchline, use slang like 'криндж', 'лол', 'трушно', 'прикол', and emojis 🤯🔥. "
        "Keep the social justice angle but make it sound like a stand-up bit—zero fluff, zero formal tone!"
    )
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": text}
        ],
        max_completion_tokens=800,
        temperature=1
    )
    return resp.choices[0].message.content.strip()


def translate_right(text):
    """Translate text to coarse, right-wing Russian bidlo slang"""
    prompt = (
        "You are an unfiltered Russian Gen Z 'bidlo' armed with savage sarcasm. "
        "Rewrite the news entirely in Russian, using coarse, blunt bidlo slang—no English sentences whatsoever, only Russian loanwords. "
        "Deliver one gut-punch barb that drips disdain, use words like 'хуяк', 'патриот', 'бабки', and emojis 💀🤑. "
        "Crush leftist squeals, but keep the facts intact—full venom, zero vanilla."
    )
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": text}
        ],
        max_completion_tokens=800,
        temperature=1
    )
    return resp.choices[0].message.content.strip()

async def main():
    """Main test function"""
    logger.info("Starting dual-style test run")
    if not all([API_ID, API_HASH, OPENAI_KEY, SRC_CHANNEL, DST_CHANNEL]):
        logger.error("Missing required environment variables!")
        return

    async with TelegramClient(SESSION, API_ID, API_HASH) as tg_client:
        logger.info(f"Fetching latest post from {SRC_CHANNEL}")
        msgs = await tg_client.get_messages(SRC_CHANNEL, limit=1)
        if not msgs or not msgs[0].text:
            logger.error("No valid message found")
            return
        text = msgs[0].text

        # Left-leaning translation
        logger.info("Translating LEFT style...")
        left = translate_left(text)
        logger.info(f"LEFT translation snippet: {left[:100]}...")
        # Post heading then the translation
        await tg_client.send_message(DST_CHANNEL, "🟢 LEFT-ZOOMER VERSION:")
        await tg_client.send_message(DST_CHANNEL, left)
        logger.info("Posted left-leaning version and translation")

        # Right-wing translation
        logger.info("Translating RIGHT style...")
        right = translate_right(text)
        logger.info(f"RIGHT translation snippet: {right[:100]}...")
        # Post heading then the translation
        await tg_client.send_message(DST_CHANNEL, "🔴 RIGHT-BIDLO VERSION:")
        await tg_client.send_message(DST_CHANNEL, right)
        logger.info("Posted right-wing version and translation")

        logger.info("Dual test run complete!")

if __name__ == "__main__":
    asyncio.run(main()) 