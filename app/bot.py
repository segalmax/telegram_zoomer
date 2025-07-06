#!/usr/bin/env python3
"""
Telegram Zoomer Bot - Translates posts into zoomer slang
"""

import os
import asyncio
import logging
import time
import sys
import uuid
from pathlib import Path
from telethon import TelegramClient, events
from telethon.network import ConnectionTcpAbridged
from telethon.sessions import StringSession
import anthropic
from dotenv import load_dotenv
from .translator import get_anthropic_client, translate_and_link

from .session_manager import setup_session, save_session_after_auth
from telethon.errors import SessionPasswordNeededError
from datetime import datetime, timedelta
import argparse

from .vector_store import recall as recall_tm, save_pair as store_tm
from .article_extractor import extract_article
from .analytics import analytics
# Using translate_and_link for unified semantic linking

# Load environment variables explicitly from project root.
# Order of loading determines precedence for non-secret variables if keys overlap.
# 1. app_settings.env: for non-secret app configurations. These will override OS env vars if present.
# 2. .env: for secrets. These will NOT override anything already set by OS or app_settings.env.

project_root = Path(__file__).resolve().parent.parent

# Load non-secret app settings (e.g., channel names, feature flags)
# These will take precedence over OS environment variables for the same keys.
load_dotenv(dotenv_path=project_root / 'app_settings.env', override=True)

# Load secrets from .env file.
# These will only be loaded if not already present in the environment (e.g., from OS or app_settings.env).
load_dotenv(dotenv_path=project_root / '.env', override=False)

# Get configuration from environment variables
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
PHONE = os.getenv('PHONE') or os.getenv('TG_PHONE')  # Check both variable names

SRC_CHANNEL = os.getenv('SRC_CHANNEL')
DST_CHANNEL = os.getenv('DST_CHANNEL')

ANTHROPIC_KEY = os.getenv('ANTHROPIC_API_KEY')


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger('app.bot')

# Check for TEST_SRC_CHANNEL and TEST_DST_CHANNEL environment variables
# This helps us switch to test mode when running tests
TEST_MODE = False
if os.getenv('TEST_MODE', 'false').lower() == 'true':
    TEST_MODE = True
    logger.info("Running in TEST MODE")
    # Use test channels if they are defined
    if os.getenv('TEST_SRC_CHANNEL'):
        SRC_CHANNEL = os.getenv('TEST_SRC_CHANNEL')
        logger.info(f"Using TEST source channel: {SRC_CHANNEL}")
    if os.getenv('TEST_DST_CHANNEL'):
        DST_CHANNEL = os.getenv('TEST_DST_CHANNEL')
        logger.info(f"Using TEST destination channel: {DST_CHANNEL}")

# Configuration from environment variables
try:
    API_ID = int(os.getenv('TG_API_ID'))
    API_HASH = os.getenv('TG_API_HASH')
    ANTHROPIC_KEY = os.getenv('ANTHROPIC_API_KEY')
except (TypeError, ValueError) as e:
    logger.error(f"Error: TG_API_ID, TG_API_HASH, or ANTHROPIC_API_KEY is not set correctly in .env: {e}")
    sys.exit("Critical environment variables missing or invalid. Exiting.")

TG_PHONE = os.getenv('TG_PHONE') # Optional, bot will prompt

# Use session manager to handle session persistence
SESSION = setup_session()

if not SRC_CHANNEL or not DST_CHANNEL:
    logger.error("Error: SRC_CHANNEL or DST_CHANNEL is not set in .env.")
    sys.exit("Source/Destination channel environment variables missing. Exiting.")

# Initialize Anthropic client
anthropic_client = None
if ANTHROPIC_KEY:
    anthropic_client = get_anthropic_client(ANTHROPIC_KEY)
else:
    logger.error("ANTHROPIC_API_KEY not found. Translation functions will fail.")
    # Decide if this is fatal or if bot can run without Anthropic (e.g. only relaying)

async def translate_and_post(client_instance, txt, message_id=None, destination_channel=None, message_entity_urls=None):
    # Renamed client to client_instance to avoid conflict with openai_client module
    try:
        start_time = time.time()
        logger.info(f"Starting translation and posting for message ID: {message_id}")
        
        # Start analytics session
        article_url = message_entity_urls[0] if message_entity_urls else None
        session_id = analytics.start_session(str(message_id) if message_id else None, txt, article_url)
        
        dst_channel_to_use = destination_channel or DST_CHANNEL
        logger.info(f"Using destination channel: {dst_channel_to_use}")

        # Get the original message link format: https://t.me/c/CHANNEL_ID/MESSAGE_ID
        # or for public channels: https://t.me/CHANNEL_NAME/MESSAGE_ID
        message_link = f"https://t.me/{SRC_CHANNEL.replace('@', '')}/{message_id}" if message_id else "Unknown source"
        logger.info(f"Original message link: {message_link}")

        # Include both the original message link and any extracted URLs from message entities
        # Format as hyperlinks to hide the full URLs
        source_footer = f"\n\n🔗 [Оригинал:]({message_link})"
        
        # Add extracted links from message entities if available
        if message_entity_urls and len(message_entity_urls) > 0:
            source_footer += f"\n🔗 [Ссылка из статьи]({message_entity_urls[0]})"
            logger.info(f"Including extracted URL from message: {message_entity_urls[0]}")
        
        async def send_message_parts(channel, text_content):
            """Send message parts and return the sent message object for navigation link tracking."""
            sent_message = await client_instance.send_message(channel, text_content, parse_mode='md')
            return sent_message

        # Check for Anthropic client *before* attempting to translate
        if not anthropic_client:
            logger.error("Cannot translate without Anthropic client.")
            return False
        
        # ------------- translation-memory context ----------------
        translation_context = txt
        memory_start_time = time.time()
        try:
            logger.info(f"🧠 Querying translation memory for message {message_id} (k=10)")
            logger.debug(f"🔍 Query text preview: {txt[:100]}...")
            
            memory = recall_tm(txt, k=10)  # Increased from k=5 to k=10
            memory_query_time = time.time() - memory_start_time
            
            if memory:
                logger.info(f"✅ Found {len(memory)} relevant memories in {memory_query_time:.3f}s")
                
                # Log detailed memory analysis
                for i, m in enumerate(memory, 1):
                    similarity = m.get('similarity', 0.0)
                    source_preview = m.get('source_text', '')[:60] + "..." if len(m.get('source_text', '')) > 60 else m.get('source_text', '')
                    translation_preview = m.get('translation_text', '')[:60] + "..." if len(m.get('translation_text', '')) > 60 else m.get('translation_text', '')
                    logger.info(f"  📝 Memory {i}: similarity={similarity:.3f}")
                    logger.debug(f"    Source: {source_preview}")
                    logger.debug(f"    Translation: {translation_preview}")
                
                # Calculate memory statistics
                similarities = [m.get('similarity', 0.0) for m in memory]
                avg_similarity = sum(similarities) / len(similarities) if similarities else 0
                max_similarity = max(similarities) if similarities else 0
                min_similarity = min(similarities) if similarities else 0
                
                logger.info(f"📊 Memory stats: avg_sim={avg_similarity:.3f}, max_sim={max_similarity:.3f}, min_sim={min_similarity:.3f}")
                
                # Track memory metrics in analytics
                analytics.set_memory_metrics(memory, int(memory_query_time * 1000))
                analytics.track_memory_usage(session_id, memory)
                
                # Don't add full memory dump to user context - Claude gets compact summaries in system prompt
                # This prevents context overload that can cause poor linking decisions
                logger.info(f"🔄 Memory context will be provided via system prompt, not user message")
                
                logger.info(f"🔄 Translation context: {len(translation_context)} chars (memory provided separately via system prompt)")
            else:
                logger.warning(f"❌ No memories found for message {message_id} in {memory_query_time:.3f}s")
                analytics.set_memory_metrics([], int(memory_query_time * 1000))
                
        except Exception as e:
            memory_query_time = time.time() - memory_start_time
            logger.error(f"💥 TM recall failed for message {message_id} after {memory_query_time:.3f}s: {e}", exc_info=True)
        
        # Append article content (runs after TM injection, before translation)
        if message_entity_urls and len(message_entity_urls) > 0:
            article_text = extract_article(message_entity_urls[0])
            if article_text:
                translation_context += f"\n\nArticle content from {message_entity_urls[0]}:\n{article_text}"
                logger.info(f"Added article content ({len(article_text)} chars) to translation context")
                analytics.set_article_content(article_text)
            else:
                translation_context += f"\n\nNote: This message contains a link: {message_entity_urls[0]}"
                logger.info("Article extraction failed, using fallback link mention")
        
        # Always use modern Lurkmore style for Israeli Russian audience (only style supported)
        logger.info("Translating in modern Lurkmore style for Israeli Russian audience with editorial system...")
        translation_start = time.time()
        linked_text, conversation_log = await translate_and_link(anthropic_client, translation_context, memory)
        translation_time_ms = int((time.time() - translation_start) * 1000)
        
        # Track translation result (extract text without links for analytics)
        analytics.set_translation_result(linked_text, translation_time_ms)

        logger.info("Safety check disabled - posting Lurkmore-style translation with navigation links")
        
        # Add invisible article link at the beginning for proper Telegram thumbnail
        invisible_article_link = ""
        if message_entity_urls and len(message_entity_urls) > 0:
            invisible_article_link = f"[\u200B]({message_entity_urls[0]})"
            logger.info(f"Added invisible article link for thumbnail: {message_entity_urls[0]}")
        
        right_content = f"{invisible_article_link}{linked_text}{source_footer}"
        logger.info(f"📝 Final post content preview: {right_content[:200]}...")
        sent_message = await send_message_parts(dst_channel_to_use, right_content)
        logger.info(f"Posted modern Lurkmore style version")
        
        # Persist pair in translation memory (best-effort) 
        save_start_time = time.time()
        try:
            pair_id = f"{message_id}-right" if message_id else str(uuid.uuid4())
            logger.info(f"💾 Saving translation pair to memory: {pair_id}")
            logger.debug(f"📝 Source length: {len(txt)} chars, Translation length: {len(linked_text)} chars")
            
            # Construct destination message URL from the sent message
            destination_message_url = None
            if sent_message and hasattr(sent_message, 'id'):
                # Remove @ from channel name and construct t.me URL
                dest_channel_clean = dst_channel_to_use.replace("@", "")
                destination_message_url = f"https://t.me/{dest_channel_clean}/{sent_message.id}"
                logger.info(f"🔗 Constructed destination URL: {destination_message_url}")
            
            store_tm(
                src=txt,
                tgt=linked_text,
                pair_id=pair_id,
                message_id=sent_message.id if sent_message else message_id,
                channel_name=dst_channel_to_use.replace("@", ""),
                message_url=destination_message_url,
                conversation_log=conversation_log,
            )
            save_time = time.time() - save_start_time
            logger.info(f"✅ Translation pair saved successfully in {save_time:.3f}s: {pair_id}")
            
            # Track save time in analytics
            analytics.set_memory_save_time(int(save_time * 1000))
            
        except Exception as e:
            save_time = time.time() - save_start_time
            logger.error(f"💥 TM save failed for {pair_id} after {save_time:.3f}s: {e}", exc_info=True)
            analytics.set_error(f"Memory save failed: {e}")
        
        logger.info(f"Total processing time for message: {time.time() - start_time:.2f} seconds")
        
        # End analytics session
        analytics.end_session()
        
        return sent_message
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}", exc_info=True)
        
        # Mark session as failed and end it
        analytics.set_error(str(e))
        analytics.end_session()
        
        return False

async def setup_event_handlers(client_instance):
    # Renamed client to client_instance
    @client_instance.on(events.NewMessage(chats=SRC_CHANNEL))
    async def handle_new_message(event):
        try:
            txt = event.message.message
            if not txt: return
            logger.info(f"Processing new message ID {event.message.id}: {txt[:50]}...")
            
            # Extract URLs from message entities
            message_entity_urls = []
            if hasattr(event.message, 'entities') and event.message.entities:
                for entity in event.message.entities:
                    if hasattr(entity, 'url') and entity.url:
                        # Entity already has URL property
                        message_entity_urls.append(entity.url)
                        logger.info(f"Found URL entity with direct URL: {entity.url}")
                    elif hasattr(entity, '_') and entity._ == 'MessageEntityTextUrl':
                        # TextUrl entity type
                        if hasattr(entity, 'url'):
                            message_entity_urls.append(entity.url)
                            logger.info(f"Found TextUrl entity: {entity.url}")
                    elif hasattr(entity, '_') and entity._ in ('MessageEntityUrl', 'MessageEntityTextUrl'):
                        # Extract URL from the message text using offset and length
                        if hasattr(entity, 'offset') and hasattr(entity, 'length'):
                            url_text = txt[entity.offset:entity.offset + entity.length]
                            if url_text.startswith('http'):
                                message_entity_urls.append(url_text)
                                logger.info(f"Extracted URL from text: {url_text}")
                            else:
                                logger.info(f"Found URL-like entity but not a valid URL: {url_text}")
            
            logger.info(f"Extracted URLs from message: {message_entity_urls}")
            
            sent_message = await translate_and_post(client_instance, txt, event.message.id, message_entity_urls=message_entity_urls)
            if sent_message:
                logger.info(f"Successfully processed and posted message ID {event.message.id}")
        except Exception as e:
            logger.error(f"Error in handle_new_message: {str(e)}", exc_info=True)

async def process_recent_posts(client_instance, limit=10, timeout=300):
    # Renamed client to client_instance
    try:
        logger.info(f"Begin processing {limit} most recent posts from channel '{SRC_CHANNEL}'")
        start_time = time.time()
        fetch_timeout = min(60, timeout / 2)
        try:
            messages = await asyncio.wait_for(
                client_instance.get_messages(SRC_CHANNEL, limit=limit), 
                timeout=fetch_timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"Timed out fetching messages from '{SRC_CHANNEL}'")
            return 0
        
        assert messages, f"No messages found in '{SRC_CHANNEL}' - this indicates a configuration or access problem"
        
        processed_count = 0
        for msg in reversed(messages):
            if not msg.text: continue
            if time.time() - start_time > timeout - 30: # Reserve 30s
                logger.warning("Approaching timeout, stopping batch processing.")
                break
            logger.info(f"Processing message {msg.id}: {msg.text[:50]}...")
            
            # Extract URLs from message entities
            message_entity_urls = []
            if hasattr(msg, 'entities') and msg.entities:
                for entity in msg.entities:
                    if hasattr(entity, 'url') and entity.url:
                        # Entity already has URL property
                        message_entity_urls.append(entity.url)
                        logger.info(f"Found URL entity with direct URL: {entity.url}")
                    elif hasattr(entity, '_') and entity._ == 'MessageEntityTextUrl':
                        # TextUrl entity type
                        if hasattr(entity, 'url'):
                            message_entity_urls.append(entity.url)
                            logger.info(f"Found TextUrl entity: {entity.url}")
                    elif hasattr(entity, '_') and entity._ in ('MessageEntityUrl', 'MessageEntityTextUrl'):
                        # Extract URL from the message text using offset and length
                        if hasattr(entity, 'offset') and hasattr(entity, 'length'):
                            url_text = msg.text[entity.offset:entity.offset + entity.length]
                            if url_text.startswith('http'):
                                message_entity_urls.append(url_text)
                            else:
                                logger.info(f"Found URL-like entity but not a valid URL: {url_text}")
            
            logger.info(f"Extracted URLs from message: {message_entity_urls}")
            
            processing_msg_timeout = min(180, (timeout - (time.time() - start_time)) / (len(messages) - processed_count + 1))
            try:
                sent_message = await asyncio.wait_for(
                    translate_and_post(client_instance, msg.text, msg.id, message_entity_urls=message_entity_urls),
                    timeout=processing_msg_timeout
                )
                if sent_message: processed_count += 1
            except asyncio.TimeoutError:
                logger.error(f"Timed out processing message {msg.id}")
            except Exception as e:
                logger.error(f"Error processing message {msg.id}: {str(e)}", exc_info=True)
            await asyncio.sleep(1) # Rate limit
        logger.info(f"Batch processing completed. Processed {processed_count}/{len(messages)} messages")
        return processed_count
    except Exception as e:
        logger.error(f"Error in batch processing: {str(e)}", exc_info=True)
        return 0



async def process_recent_messages(client, count):
    """Process a specified number of recent messages from source channel"""
    try:
        logger.info(f"Processing {count} recent messages from {SRC_CHANNEL}")
        
        # Get the most recent messages from source channel
        messages = await client.get_messages(SRC_CHANNEL, limit=count)
        
        # Process each message, starting from oldest (reverse order)
        for msg in reversed(messages):
            if not msg.text:
                continue
            
            # Extract URLs from message entities
            message_entity_urls = []
            if hasattr(msg, 'entities') and msg.entities:
                for entity in msg.entities:
                    if hasattr(entity, 'url') and entity.url:
                        message_entity_urls.append(entity.url)
                    elif hasattr(entity, '_') and entity._ in ('MessageEntityUrl', 'MessageEntityTextUrl'):
                        if hasattr(entity, 'offset') and hasattr(entity, 'length'):
                            url_text = msg.text[entity.offset:entity.offset + entity.length]
                            if url_text.startswith('http'):
                                message_entity_urls.append(url_text)
            
            logger.info(f"Processing message ID: {msg.id}")
            sent_message = await translate_and_post(client, msg.text, msg.id, message_entity_urls=message_entity_urls)
            
            # Add a short delay between processing messages
            await asyncio.sleep(1)
            
        logger.info(f"Completed processing {count} recent messages")
        return True
    except Exception as e:
        logger.exception(f"Error processing recent messages: {e}")
        return False





async def main():
    """
    Main entry point for the Zoomer Bot.
    Sets up Telegram client, event handlers, and starts the client.
    """
    parser = argparse.ArgumentParser(description='Telegram Zoomer Bot - Translate messages with Artemiy Lebedev style')
    parser.add_argument('--process-recent', type=int, help='Process the specified number of recent messages')
    args = parser.parse_args()
    
    try:
        # Create Telegram client
        logger.info(f"Creating Telegram client with session: {SESSION}")
        client = TelegramClient(
            SESSION,
            int(API_ID), 
            API_HASH,
            connection=ConnectionTcpAbridged
        )
        
        # Set up event handler
        await setup_event_handlers(client)
        
        # Connect to Telegram
        logger.info("Starting Telegram client...")
        await client.start(phone=TG_PHONE)
        
        # Save session to database after successful authentication
        save_session_after_auth(client)
        
        # In TEST_MODE process recent messages immediately so that polling-flow test which sends the
        # message *before* the bot starts can still be picked up.
        if TEST_MODE and os.getenv("TEST_RUN_MESSAGE_PREFIX"):
            try:
                await process_recent_posts(client, limit=20, timeout=120)
            except Exception as e:
                logger.warning(f"TEST_MODE pre-processing recent posts failed: {e}")
        
        # Process recent messages if requested
        if args.process_recent and args.process_recent > 0:
            logger.info(f"Processing {args.process_recent} recent messages")
            messages = await client.get_messages(SRC_CHANNEL, limit=args.process_recent)
            
            # Process each message
            for msg in reversed(messages):
                logger.info(f"Processing message ID: {msg.id}")
                if not msg.text: continue
                
                # Extract URLs from message entities
                message_entity_urls = []
                if hasattr(msg, 'entities') and msg.entities:
                    for entity in msg.entities:
                        if hasattr(entity, 'url') and entity.url:
                            message_entity_urls.append(entity.url)
                        elif hasattr(entity, '_') and entity._ in ('MessageEntityUrl', 'MessageEntityTextUrl'):
                            if hasattr(entity, 'offset') and hasattr(entity, 'length'):
                                url_text = msg.text[entity.offset:entity.offset + entity.length]
                                if url_text.startswith('http'):
                                    message_entity_urls.append(url_text)
                
                sent_message = await translate_and_post(client, msg.text, msg.id, message_entity_urls=message_entity_urls)
                await asyncio.sleep(2)  # Add delay between processing
            
            logger.info("Finished processing recent messages")
            logger.info("🏁 Exiting after processing recent messages (not starting polling mode)")
            return  # Exit after processing recent messages, don't start polling
        
        logger.info(f"Client ready, listening for new messages on: {SRC_CHANNEL}")
        await client.run_until_disconnected()
        
    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 