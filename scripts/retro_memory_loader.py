#!/usr/bin/env python3
"""
Backfill Translation Memory with past translations.

* Fetches the last N posts from the destination channel (DST_CHANNEL).
* Extracts the original source message via the link in the footer.
* Saves (source_text, translation_text) pairs into Supabase via vector_store.save_pair.

Usage:
    python scripts/retro_memory_loader.py [--limit 50]

Environment:
    Relies on the same variables as app/bot.py (API_ID, API_HASH, SRC_CHANNEL, DST_CHANNEL, etc.)
    and a valid Telethon session (managed by session_manager.py).
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Tuple

from dotenv import load_dotenv
from telethon import events
from telethon.tl.types import Message, InputChannel
from telethon import utils
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.errors import RPCError
import telethon

# Project imports
project_root = Path(__file__).resolve().parent.parent
load_dotenv(project_root / "app_settings.env", override=True)
load_dotenv(project_root / ".env", override=False)

from app.session_manager import setup_session  # noqa: E402  pylint: disable=wrong-import-position
from app import vector_store  # noqa: E402  pylint: disable=wrong-import-position

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("retro_loader")

API_ID = os.getenv("TG_API_ID")
API_HASH = os.getenv("TG_API_HASH")
SRC_CHANNEL = os.getenv("SRC_CHANNEL")
DST_CHANNEL = os.getenv("DST_CHANNEL")

if not API_ID or not API_HASH or not SRC_CHANNEL or not DST_CHANNEL:
    logger.error("Missing required env vars (TG_API_ID, TG_API_HASH, SRC_CHANNEL, DST_CHANNEL)")
    sys.exit(1)

API_ID = int(API_ID)

ORIGINAL_LINK_RE = re.compile(r"https?://t\.me/[^/]+/(?P<msg_id>\d+)")


def extract_translation_text(full_text: str) -> str:
    """Strip footer links from a posted translation message."""
    if not full_text:
        return ""
    # Translation text ends before the first double line break + link block starting with '🔗'
    parts = full_text.split("\n\n🔗", 1)
    return parts[0].strip()


def extract_original_msg_id(full_text: str) -> int | None:
    """Find original message id from the 'Оригинал' link in the footer."""
    match = ORIGINAL_LINK_RE.search(full_text)
    if match:
        try:
            return int(match.group("msg_id"))
        except ValueError:
            return None
    return None


async def process_history(limit: int = 50) -> None:
    """Main coroutine to process destination channel history."""
    logger.info("Starting retro-memory backfill: last %d posts", limit)
    session = setup_session()
    async with telethon.TelegramClient(session, API_ID, API_HASH) as client:
        # Resolve channels
        src_ent = await client.get_entity(SRC_CHANNEL)
        dst_ent = await client.get_entity(DST_CHANNEL)

        messages: list[Message] = await client.get_messages(dst_ent, limit=limit)
        processed = 0
        saved = 0

        for msg in reversed(messages):  # oldest first
            processed += 1
            if not msg.text:
                continue

            translation_text = extract_translation_text(msg.text)
            if not translation_text:
                logger.debug("Message %d has no translation text after stripping footer; skipping", msg.id)
                continue

            orig_id = extract_original_msg_id(msg.text)
            if orig_id is None:
                logger.debug("Could not find original message link in DST message %d; skipping", msg.id)
                continue

            try:
                src_msg = await client.get_messages(src_ent, ids=orig_id)
            except RPCError as e:
                logger.warning("Failed to fetch original message %d: %s", orig_id, e)
                continue

            source_text = src_msg.text or ""

            # If the original message contains a URL to an article, extract & scrape it
            article_text = ""
            if hasattr(src_msg, "entities") and src_msg.entities:
                for ent in src_msg.entities:
                    url = None
                    if hasattr(ent, "url") and ent.url:
                        url = ent.url
                    elif getattr(ent, "_", "") in ("MessageEntityUrl", "MessageEntityTextUrl"):
                        # Derive raw slice
                        if hasattr(ent, "offset") and hasattr(ent, "length"):
                            url_candidate = src_msg.raw_text[ent.offset : ent.offset + ent.length]
                            if url_candidate.startswith("http"):
                                url = url_candidate
                    if url and url.startswith("http") and not url.startswith("https://t.me"):
                        try:
                            from app.article_extractor import extract_article  # lazy import

                            article_text = extract_article(url) or ""
                            if article_text:
                                logger.debug("Fetched %d chars of article text from %s", len(article_text), url)
                                break  # use first valid article
                        except Exception as e:
                            logger.warning("Article extraction failed for %s: %s", url, e)

            # Combine message + article (if any) for embedding
            combined_source = source_text
            if article_text:
                combined_source += f"\n\n{article_text}"

            if not combined_source.strip():
                logger.debug("Source + article empty for message %d; skipping", orig_id)
                continue

            pair_id = f"retro-{orig_id}"
            vector_store.save_pair(combined_source, translation_text, pair_id=pair_id)
            saved += 1
            logger.info("Saved TM pair for src msg %d (dst msg %d)", orig_id, msg.id)

        logger.info("Retro-memory backfill completed. Processed %d messages, saved %d pairs.", processed, saved)


def main():
    parser = argparse.ArgumentParser(description="Backfill translation memory with past posts.")
    parser.add_argument("--limit", type=int, default=50, help="Number of recent destination messages to scan (default 50)")
    args = parser.parse_args()

    asyncio.run(process_history(limit=args.limit))


if __name__ == "__main__":
    main() 