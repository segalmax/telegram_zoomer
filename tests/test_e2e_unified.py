"""
Unified test script for Telegram Zoomer Bot (pytest-harnessed)

This script provides complete end-to-end testing:
1. API Integration - Tests OpenAI and Stability AI
2. Telegram Pipeline - Tests the full message flow through Telegram
3. Bot Mode - Runs the bot against test channels for E2E validation.

Usage (pytest):
  pytest tests/test_e2e_unified.py                 # Run standard E2E flow
  pytest tests/test_e2e_unified.py --bot-mode      # Run in bot mode
  pytest tests/test_e2e_unified.py --stability     # Test with Stability AI
  pytest tests/test_e2e_unified.py --no-images     # Disable image generation
  pytest tests/test_e2e_unified.py --new-session   # Force new Telegram session
  pytest tests/test_e2e_unified.py --process-recent N # Process N recent messages in bot mode
"""

import os
import sys
import uuid
import asyncio
import logging
# import argparse # Replaced by pytest fixtures
import time
from io import BytesIO
from dotenv import load_dotenv
import openai
from pathlib import Path
import json
import pytest # Added pytest

# Assuming app modules are in the parent directory's 'app' folder
# Adjust sys.path if necessary, or install the app as a package
# For now, direct import if 'app' is discoverable (e.g. via PYTHONPATH or project structure)
import app.bot
from app.translator import get_anthropic_client, translate_text
from app.image_generator import generate_image_for_post, generate_image_with_stability_ai
# Original bot.main is renamed to bot_main_entry for clarity to avoid confusion with this script's previous main
from app.bot import main as bot_main_entry, translate_and_post as original_bot_translate_and_post
from app.pts_manager import load_pts, save_pts

# Try to import Telegram if needed
try:
    from telethon import TelegramClient
    from telethon.network import ConnectionTcpAbridged
    from telethon import events
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False
    # Pytest will skip tests that require telethon if this is False

# Load environment variables
# project_root should be the actual project root, not tests/
project_root = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=project_root / 'app_settings.env', override=True)
load_dotenv(dotenv_path=project_root / '.env', override=False)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s', # Added name and levelname
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__) # Use __name__ for specific logger

# Configuration
ANTHROPIC_KEY = os.getenv('ANTHROPIC_API_KEY')
TEST_MESSAGE = (
    "BREAKING NEWS: Scientists discover remarkable new species of bioluminescent deep-sea creatures "
    "near hydrothermal vents in the Pacific Ocean. The colorful organisms have evolved unique "
    "adaptations to extreme pressure and toxic chemicals that could provide insights into early life on Earth. "
    "Read more at https://www.nytimes.com/2023/05/06/science/deep-sea-creatures.html"
)

API_ID = os.getenv('TG_API_ID')
API_HASH = os.getenv('TG_API_HASH')
TG_PHONE = os.getenv('TG_PHONE')
TEST_SRC_CHANNEL = os.getenv('TEST_SRC_CHANNEL')
TEST_DST_CHANNEL = os.getenv('TEST_DST_CHANNEL')

TEST_RUN_MESSAGE_PREFIX = os.getenv('TEST_RUN_MESSAGE_PREFIX')
BOT_MODE_TIMEOUT = int(os.getenv('TEST_BOT_MODE_TIMEOUT', '60'))

PERSISTENT_TEST_SESSION = "session/test_session_persistent"

if TEST_SRC_CHANNEL:
    os.environ['TEST_SRC_CHANNEL'] = TEST_SRC_CHANNEL
if TEST_DST_CHANNEL:
    os.environ['TEST_DST_CHANNEL'] = TEST_DST_CHANNEL

@pytest.mark.asyncio
async def test_api_translations(test_args):
    """Test translation functionality with Anthropic Claude."""
    client = get_anthropic_client(ANTHROPIC_KEY)
    assert client, "Anthropic client could not be initialized. Check ANTHROPIC_API_KEY."
    logger.info("Testing RIGHT-BIDLO style translation...")
    translation_result = await translate_text(client, TEST_MESSAGE)
    assert translation_result and len(translation_result) > 10, "RIGHT-BIDLO translation failed or returned empty/short result"
    logger.info(f"RIGHT-BIDLO translation successful: {translation_result[:100]}...")

@pytest.mark.asyncio
async def test_api_image_generation_dalle(test_args):
    """Test image generation with DALL-E."""
    if test_args.no_images:
        pytest.skip("Image generation disabled by --no-images flag")
    if test_args.stability:
        pytest.skip("Skipping DALL-E test when --stability is enabled")

    # Image generation still uses OpenAI for DALL-E
    openai_key = os.getenv('OPENAI_API_KEY')
    if not openai_key:
        pytest.skip("OPENAI_API_KEY not found, skipping DALL-E test")
    
    from app.image_generator import get_openai_client
    client = get_openai_client(openai_key)
    assert client, "OpenAI client could not be initialized. Check OPENAI_API_KEY."
    logger.info("Testing DALL-E image generation...")
    longer_test_text = (
        "BREAKING NEWS: Scientists discover fascinating new species of deep-sea creatures "
        "near hydrothermal vents in the Pacific Ocean. The newly discovered species include "
        "unique adaptations to extreme pressure and temperature conditions found in these depths."
    )
    # Set USE_STABILITY_AI to false for this DALL-E specific test
    original_stability_env = os.environ.pop('USE_STABILITY_AI', None)
    os.environ['GENERATE_IMAGES'] = 'true' # Ensure images are on for this specific test
    try:
        result = await generate_image_for_post(client, longer_test_text)
        assert result, "DALL-E image generation failed or returned None"
        if isinstance(result, BytesIO):
            image_data = result.getvalue()
            assert len(image_data) > 1000, f"DALL-E image data too small: {len(image_data)} bytes"
            logger.info("DALL-E image generation successful (BytesIO)")
        elif isinstance(result, str): # URL
            assert result.startswith("http"), "DALL-E returned a non-URL string"
            logger.info(f"DALL-E image generation returned a URL: {result[:50]}...")
        else:
            pytest.fail(f"Unknown result type from DALL-E: {type(result)}")
    finally:
        if original_stability_env is not None:
            os.environ['USE_STABILITY_AI'] = original_stability_env
        os.environ.pop('GENERATE_IMAGES', None)

@pytest.mark.asyncio
async def test_api_image_generation_stability(test_args):
    """Test image generation with Stability AI."""
    if test_args.no_images:
        pytest.skip("Image generation disabled by --no-images flag")
    if not test_args.stability:
        pytest.skip("Skipping Stability AI test; --stability flag not provided.")
    if not os.getenv('STABILITY_AI_API_KEY'):
        pytest.skip("STABILITY_AI_API_KEY not found, skipping Stability AI test")

    logger.info("Testing Stability AI image generation...")
    # Set USE_STABILITY_AI to true for this Stability specific test
    original_stability_env = os.environ.pop('USE_STABILITY_AI', None)
    os.environ['USE_STABILITY_AI'] = 'true'
    os.environ['GENERATE_IMAGES'] = 'true' # Ensure images are on
    try:
        result = await generate_image_with_stability_ai(TEST_MESSAGE)
        assert result, "Stability AI image generation failed or returned None"
        assert isinstance(result, BytesIO), f"Unexpected result type from Stability AI: {type(result)}"
        image_data = result.getvalue()
        assert len(image_data) > 1000, f"Stability AI image data too small: {len(image_data)} bytes"
        logger.info("Stability AI image generation successful")
    finally:
        if original_stability_env is not None:
            os.environ['USE_STABILITY_AI'] = original_stability_env
        else: # If it wasn't set before, ensure it's removed
            os.environ.pop('USE_STABILITY_AI', None)
        os.environ.pop('GENERATE_IMAGES', None)


async def verify_message_in_channel(client, channel, content_fragment, timeout=300, limit=10):
    """Check if a message containing the fragment appears in the channel within timeout"""
    start_time = time.time()
    logger.info(f"VERIFY_MSG: Starting check for '{content_fragment}' in {channel} (timeout={timeout}s, limit={limit})")
    while time.time() - start_time < timeout:
        logger.debug(f"VERIFY_MSG: Querying last {limit} messages from {channel}...")
        messages = await client.get_messages(channel, limit=limit)
        if not messages:
            logger.info(f"VERIFY_MSG: No messages found in {channel}. Waiting 5s...")
            await asyncio.sleep(5)
            continue
        
        logger.debug(f"VERIFY_MSG: Found {len(messages)} messages. Iterating to find '{content_fragment}'...")
        for i, msg in enumerate(messages):
            text_to_check = []
            msg_details = f"Msg {i+1}/{len(messages)} (ID: {msg.id}): "
            if msg.text:
                text_to_check.append(msg.text.lower())
                text_preview = msg.text[:70].replace('\n', ' ')
                msg_details += f"Text=\"{text_preview}...\" "
            if msg.media and hasattr(msg, 'caption') and msg.caption:
                text_to_check.append(msg.caption.lower())
                caption_preview = msg.caption[:70].replace('\n', ' ')
                msg_details += f"Caption=\"{caption_preview}...\""
            
            logger.debug(f"VERIFY_MSG: Inspecting: {msg_details.strip()}")

            for text_item in text_to_check:
                if content_fragment.lower() in text_item:
                    logger.info(f"VERIFY_MSG: Found '{content_fragment}' in message {msg.id}: '{text_item[:100]}...'")
                    return True
        logger.info(f"VERIFY_MSG: '{content_fragment}' not found in current batch. Waiting 5s... (Time left: {timeout - (time.time() - start_time):.0f}s)")
        await asyncio.sleep(5)
    logger.error(f"VERIFY_MSG: Failed to find '{content_fragment}' in {channel} after {timeout}s")
    return False

@pytest.mark.asyncio
async def test_telegram_pipeline(test_args):
    """Run the Telegram pipeline test."""
    if not TELETHON_AVAILABLE:
        pytest.skip("Telethon not available. Please install with: pip install telethon")
    if not all([API_ID, API_HASH, TG_PHONE, TEST_SRC_CHANNEL, TEST_DST_CHANNEL]):
        pytest.fail("Missing Telegram credentials or test channels. Check .env and ensure TEST_SRC_CHANNEL/TEST_DST_CHANNEL are set.")

    # Use database-backed session for tests
    os.environ['TEST_MODE'] = 'true'
    from app.session_manager import setup_session
    test_session = setup_session()
    logger.info("Using database-backed test session")

    client = None
    original_use_stability_env = os.environ.get('USE_STABILITY_AI')
    original_generate_images_env = os.environ.get('GENERATE_IMAGES')
    original_test_mode_env = os.environ.get('TEST_MODE')

    try:
        os.environ['TEST_MODE'] = 'true'
        os.environ['USE_STABILITY_AI'] = 'true' if test_args.stability else 'false'
        os.environ['GENERATE_IMAGES'] = 'false' if test_args.no_images else 'true'
        
        stability_status = "enabled" if test_args.stability else "disabled"
        images_status = "disabled" if test_args.no_images else "enabled"
        logger.info(f"Telegram test: Stability AI {stability_status}, Images {images_status}")

        client = TelegramClient(
            test_session, int(API_ID), API_HASH,
            connection=ConnectionTcpAbridged,
            device_model="Pytest Test Device",
            system_version="Pytest Test OS",
            app_version="Zoomer Bot Pytest 1.0"
        )
        logger.info("Starting Telegram client with database session...")
        await client.start(phone=TG_PHONE)
        
        # Save session to database after successful authentication
        from app.session_manager import save_session_after_auth
        save_session_after_auth(client, "test_session", "test")
        assert await client.is_user_authorized(), "Telegram client not authorized."
        logger.info("Successfully connected and authenticated to Telegram")

        logger.info(f"Sending test message to {TEST_SRC_CHANNEL}...")
        from telethon.tl.types import MessageEntityTextUrl
        test_url = None
        if "http" in TEST_MESSAGE:
            url_start = TEST_MESSAGE.find("http")
            url_end = TEST_MESSAGE.find(" ", url_start)
            if url_end == -1: url_end = len(TEST_MESSAGE)
            test_url = TEST_MESSAGE[url_start:url_end]
        
        text_content_for_message = TEST_MESSAGE 
        entity = None
        if test_url:
            url_offset = text_content_for_message.find(test_url)
            url_length = len(test_url)
            entity = MessageEntityTextUrl(offset=url_offset, length=url_length, url=test_url)
        
        sent_msg = await client.send_message(
            TEST_SRC_CHANNEL, 
            text_content_for_message,
            formatting_entities=[entity] if entity else None
        )
        assert sent_msg, f"Failed to send message to {TEST_SRC_CHANNEL}"
        logger.info(f"Test message sent successfully with ID: {sent_msg.id}")

        message_entity_urls = []
        if hasattr(sent_msg, 'entities') and sent_msg.entities:
            for ent in sent_msg.entities:
                if hasattr(ent, 'url') and ent.url: message_entity_urls.append(ent.url)
                elif hasattr(ent, '_') and ent._ in ('MessageEntityUrl', 'MessageEntityTextUrl'):
                    if hasattr(ent, 'offset') and hasattr(ent, 'length'):
                        url_text = sent_msg.text[ent.offset:ent.offset + ent.length]
                        if url_text.startswith('http'): message_entity_urls.append(url_text)

        logger.info(f"Processing test message {sent_msg.id} directly using app.bot.translate_and_post...")
        success = await app.bot.translate_and_post(
            client,
            sent_msg.text, 
            sent_msg.id,
            destination_channel=TEST_DST_CHANNEL,
            message_entity_urls=message_entity_urls
        )
        assert success, "app.bot.translate_and_post returned False indicating failure"
        logger.info("✅ app.bot.translate_and_post completed successfully")

        logger.info(f"Verifying translated message in {TEST_DST_CHANNEL}...")
        # Look for Russian text indicating successful translation (common Russian words)
        right_verified = await verify_message_in_channel(client, TEST_DST_CHANNEL, "Оригинал", timeout=90) # Look for source attribution
        assert right_verified, "Failed to verify translated message in destination channel"

        logger.info("Verifying source attribution appears in posted message...")
        source_verified = await verify_message_in_channel(client, TEST_DST_CHANNEL, "Оригинал:", timeout=60, limit=15)
        assert source_verified, "Failed to verify source attribution in posted messages"

        if message_entity_urls:
            logger.info(f"Verifying article link fragment '{message_entity_urls[0]}'...")
            article_link_verified = await verify_message_in_channel(client, TEST_DST_CHANNEL, message_entity_urls[0], timeout=60, limit=20)
            assert article_link_verified, f"Failed to verify article link fragment '{message_entity_urls[0]}' in destination channel"

        if not test_args.no_images:
            logger.info("Verifying image was posted (since --no-images is false)...")
            messages = await client.get_messages(TEST_DST_CHANNEL, limit=15)
            has_media = any(msg.media for msg in messages if msg)
            if not has_media:
                logger.warning("No media found in recent messages in destination channel. Image might not have been posted or visible.")
            else:
                logger.info("Found message with media in destination channel.")
            # Consider adding: assert has_media, "Image was expected but not found in destination channel messages."

        logger.info("✅ Telegram pipeline test completed successfully!")

    except AssertionError:
        logger.error("❌ Telegram pipeline test failed due to an assertion.", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Error in Telegram pipeline test: {str(e)}", exc_info=True)
        pytest.fail(f"Telegram pipeline test failed with an unexpected exception: {e}")
    finally:
        if client and client.is_connected():
            await client.disconnect()
            logger.info("Disconnected from Telegram")
        # Database sessions don't need file cleanup
        logger.info("Using database-backed session - no file cleanup needed")
        
        # Restore original env vars
        if original_use_stability_env is not None: os.environ['USE_STABILITY_AI'] = original_use_stability_env
        else: os.environ.pop('USE_STABILITY_AI', None)
        if original_generate_images_env is not None: os.environ['GENERATE_IMAGES'] = original_generate_images_env
        else: os.environ.pop('GENERATE_IMAGES', None)
        if original_test_mode_env is not None: os.environ['TEST_MODE'] = original_test_mode_env
        else: os.environ.pop('TEST_MODE', None)

@pytest.mark.asyncio
async def test_run_bot_mode(test_args, bot_mode_option):
    """Runs the bot in a test mode if --bot-mode is specified."""
    if not bot_mode_option:
        pytest.skip("Skipping bot mode test; --bot-mode not specified.")

    logger.info("=== Running in REAL BOT MODE with test channels (via pytest) ===")
    assert TEST_SRC_CHANNEL and TEST_DST_CHANNEL, "TEST_SRC_CHANNEL and TEST_DST_CHANNEL must be set for bot mode"
    logger.info(f"Using test source channel: {TEST_SRC_CHANNEL}")
    logger.info(f"Using test destination channel: {TEST_DST_CHANNEL}")

    original_src_env = os.environ.get('SRC_CHANNEL')
    original_dst_env = os.environ.get('DST_CHANNEL')
    original_generate_images_env = os.environ.get('GENERATE_IMAGES')
    original_test_mode_env = os.environ.get('TEST_MODE')

    os.environ['SRC_CHANNEL'] = TEST_SRC_CHANNEL
    os.environ['DST_CHANNEL'] = TEST_DST_CHANNEL
    os.environ['TEST_MODE'] = 'true'
    os.environ['GENERATE_IMAGES'] = 'false' if test_args.no_images else 'true'
    if test_args.no_images: logger.info("Image generation disabled for bot mode")

    message_processed_event = asyncio.Event()
    async def wrapped_translate_and_post_for_bot_mode(client, txt, message_id=None, destination_channel=None, message_entity_urls=None):
        current_test_run_prefix = os.getenv('TEST_RUN_MESSAGE_PREFIX')
        if current_test_run_prefix and current_test_run_prefix in txt:
            logger.info(f"✅ BOT_MODE: Successfully processed test message with prefix: {current_test_run_prefix}")
            message_processed_event.set()
        return await original_bot_translate_and_post(client, txt, message_id, destination_channel, message_entity_urls)

    app.bot.translate_and_post = wrapped_translate_and_post_for_bot_mode
    
    original_argv = sys.argv.copy()
    bot_argv = [sys.argv[0]]
    if test_args.process_recent is not None:
        bot_argv.extend(['--process-recent', str(test_args.process_recent)])
    
    main_bot_task = None
    try:
        sys.argv = bot_argv
        logger.info(f"BOT_MODE: Starting bot_main_entry. Waiting for message with prefix '{os.getenv('TEST_RUN_MESSAGE_PREFIX', 'N/A')}' for up to {BOT_MODE_TIMEOUT}s.")
        main_bot_task = asyncio.create_task(bot_main_entry())
        done, pending = await asyncio.wait(
            [main_bot_task, asyncio.create_task(message_processed_event.wait())],
            timeout=BOT_MODE_TIMEOUT,
            return_when=asyncio.FIRST_COMPLETED
        )
        assert message_processed_event.is_set(), f"BOT_MODE: Timed out after {BOT_MODE_TIMEOUT}s waiting for message with prefix '{os.getenv('TEST_RUN_MESSAGE_PREFIX', 'N/A')}'."
        logger.info("BOT_MODE: Test message processed successfully.")
        for task in done:
            if task == main_bot_task and task.done():
                exc = task.exception()
                if exc: # pragma: no cover (hard to deterministically trigger bot failure here)
                    logger.error(f"BOT_MODE: bot_main_entry task failed: {exc}", exc_info=True)
                    pytest.fail(f"bot_main_entry task failed: {exc}")
    except asyncio.TimeoutError: # Should be caught by the assert above
        pytest.fail(f"BOT_MODE: Timed out after {BOT_MODE_TIMEOUT}s waiting for message prefix.") # pragma: no cover
    except Exception as e: # pragma: no cover
        logger.error(f"BOT_MODE: Error running bot_main_entry: {e}", exc_info=True)
        pytest.fail(f"BOT_MODE: Error running bot_main_entry: {e}")
    finally:
        if main_bot_task and not main_bot_task.done():
            main_bot_task.cancel()
            try: await main_bot_task
            except asyncio.CancelledError: logger.info("BOT_MODE: Main bot task was cancelled.")
        sys.argv = original_argv
        app.bot.translate_and_post = original_bot_translate_and_post
        if original_src_env: os.environ['SRC_CHANNEL'] = original_src_env
        else: os.environ.pop('SRC_CHANNEL', None)
        if original_dst_env: os.environ['DST_CHANNEL'] = original_dst_env
        else: os.environ.pop('DST_CHANNEL', None)
        if original_generate_images_env: os.environ['GENERATE_IMAGES'] = original_generate_images_env
        else: os.environ.pop('GENERATE_IMAGES', None)
        if original_test_mode_env is not None: os.environ['TEST_MODE'] = original_test_mode_env
        else: os.environ.pop('TEST_MODE', None)
    logger.info("🎉 Bot mode test completed.")

@pytest.mark.order(-1) # Try to run this test last in the module
def test_verify_no_errors_logged(error_counter_handler):
    """Final check for any errors logged during the test session."""
    if error_counter_handler.error_count > 0:
        messages = [f"- {rec.levelname} ({rec.name} L{rec.lineno}): {rec.getMessage()}" for rec in error_counter_handler.records]
        error_summary = "\n".join(messages)
        pytest.fail(f"{error_counter_handler.error_count} errors logged during test session:\n{error_summary}", pytrace=False)
    logger.info("✅ No critical errors logged during the test session.") 