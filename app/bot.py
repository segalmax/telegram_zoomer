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
from .autogen_translation import get_anthropic_client
from .autogen_translation import translate_and_link
from .config_loader import get_config_loader

from .session_manager import setup_session, save_session_after_auth
from telethon.errors import SessionPasswordNeededError
from datetime import datetime, timedelta
import argparse

from .vector_store import recall as recall_tm, save_pair
from .article_extractor import extract_article

# Using translate_and_link for unified semantic linking

class FlowCollector:
    """Collects production flow details for debugging/analysis without affecting core logic"""
    
    def __init__(self):
        self.steps = []
        self.start_time = None
        self.memory_query = None
        self.article_extraction = None
        self.autogen_conversation = None
        self.performance_timing = {}
        
    def start_flow(self, source_text, message_id=None):
        """Mark the start of translation flow"""
        self.start_time = time.time()
        self.log_step("flow_start", {
            "source_text_preview": source_text[:100] + "..." if len(source_text) > 100 else source_text,
            "source_text_length": len(source_text),
            "message_id": message_id,
            "timestamp": datetime.now().isoformat()
        })
    
    def log_memory_query(self, query_text, memory_results, query_time):
        """Log translation memory query details"""
        similarities = [m.get('similarity', 0.0) for m in memory_results] if memory_results else []
        
        self.memory_query = {
            "query_text_preview": query_text[:100] + "..." if len(query_text) > 100 else query_text,
            "results_count": len(memory_results) if memory_results else 0,
            "query_time_seconds": query_time,
            "similarities": similarities,
            "avg_similarity": sum(similarities) / len(similarities) if similarities else 0,
            "max_similarity": max(similarities) if similarities else 0,
            "min_similarity": min(similarities) if similarities else 0,
            "memory_preview": [
                {
                    "source_preview": m.get('source_text', '')[:60] + "..." if len(m.get('source_text', '')) > 60 else m.get('source_text', ''),
                    "translation_preview": m.get('translation_text', '')[:60] + "..." if len(m.get('translation_text', '')) > 60 else m.get('translation_text', ''),
                    "similarity": m.get('similarity', 0.0)
                }
                for m in (memory_results[:5] if memory_results else [])  # First 5 for preview
            ]
        }
        
        self.log_step("memory_query", self.memory_query)
    
    def log_article_extraction(self, url, article_text, extraction_success):
        """Log article extraction details"""
        self.article_extraction = {
            "url": url,
            "extraction_success": extraction_success,
            "article_length": len(article_text) if article_text else 0,
            "article_preview": article_text[:200] + "..." if article_text and len(article_text) > 200 else article_text
        }
        
        self.log_step("article_extraction", self.article_extraction)
    
    def log_autogen_start(self, translation_context, memory_count):
        """Log start of AutoGen conversation"""
        self.autogen_conversation = {
            "context_length": len(translation_context),
            "memory_count": memory_count,
            "start_time": time.time(),
            "conversation_messages": [],
            "initial_context_preview": translation_context[:300] + "..." if len(translation_context) > 300 else translation_context
        }
        
        self.log_step("autogen_start", {
            "context_length": len(translation_context),
            "memory_count": memory_count
        })
    
    def log_autogen_result(self, linked_text, conversation_log, translation_time):
        """Log AutoGen conversation completion"""
        if self.autogen_conversation:
            self.autogen_conversation.update({
                "final_translation": linked_text,
                "conversation_log": conversation_log,
                "translation_time_seconds": translation_time,
                "end_time": time.time()
            })
        
        self.log_step("autogen_complete", {
            "final_translation_length": len(linked_text),
            "translation_time_seconds": translation_time,
            "conversation_log_length": len(conversation_log) if conversation_log else 0
        })
    
    def log_final_content(self, final_content):
        """Log the final content that would be posted to Telegram"""
        self.final_posted_content = final_content
        self.log_step("final_content", {
            "content_length": len(final_content),
            "content_preview": final_content[:300] + "..." if len(final_content) > 300 else final_content
        })
    
    def log_step(self, step_name, details):
        """Log a flow step with timing"""
        current_time = time.time()
        elapsed = current_time - self.start_time if self.start_time else 0
        
        step = {
            "step_name": step_name,
            "timestamp": datetime.now().isoformat(),
            "elapsed_seconds": elapsed,
            "details": details
        }
        
        self.steps.append(step)
        
        # Update performance timing
        self.performance_timing[step_name] = elapsed
    
    def get_flow_summary(self):
        """Get complete flow summary for analysis"""
        total_time = time.time() - self.start_time if self.start_time else 0
        
        return {
            "total_time_seconds": total_time,
            "steps": self.steps,
            "memory_query": self.memory_query,
            "article_extraction": self.article_extraction,
            "autogen_conversation": self.autogen_conversation,
            "performance_timing": self.performance_timing,
            "final_posted_content": getattr(self, 'final_posted_content', None)
        }

# Initialize configuration loader
config = get_config_loader()

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

anthropic_client = get_anthropic_client(ANTHROPIC_KEY)

def initialize_translation_session(message_id, source_message_text, flow_collector):
    """Initialize flow logging and return start time."""
    start_time = time.time()
    logger.info(f"Starting translation and posting for message ID: {message_id}")
    
    if flow_collector:
        flow_collector.start_flow(source_message_text, message_id)
    
    return start_time

def determine_destination_channel_and_links(destination_channel, message_id):
    """Determine channel to use and create message links."""
    dst_channel_to_use = destination_channel or DST_CHANNEL
    logger.info(f"Using destination channel: {dst_channel_to_use}")

    message_link = f"https://t.me/{SRC_CHANNEL.replace('@', '')}/{message_id}" if message_id else "Unknown source"
    logger.info(f"Original message link: {message_link}")

    source_footer = f"\n\n🔗 [Оригинал:]({message_link})"
    
    return dst_channel_to_use, source_footer


def query_translation_memory(source_message_text, message_id, flow_collector):
    """Query translation memory and return memory data."""
    memory_start_time = time.time()
    memories = None
    
    try:
        logger.info(f"🧠 Querying translation memory for message {message_id} (k=10)")
        logger.debug(f"🔍 Query text preview: {source_message_text[:100]}...")
        
        memories = recall_tm(source_message_text, k=10, channel_name="nytzoomeru")
        memory_query_time = time.time() - memory_start_time
        
        if flow_collector:
            flow_collector.log_memory_query(source_message_text, memories, memory_query_time)
        
        if memories:
            log_memory_analysis(memories, memory_query_time)
        else:
            logger.warning(f"❌ No memories found for message {message_id} in {memory_query_time:.3f}s")
            
    except Exception as e:
        memory_query_time = time.time() - memory_start_time
        logger.error(f"💥 TM recall failed for message {message_id} after {memory_query_time:.3f}s: {e}", exc_info=True)
        if flow_collector:
            flow_collector.log_memory_query(source_message_text, None, memory_query_time)
    
    return memories

def log_memory_analysis(memories, memory_query_time):
    """Log detailed analysis of retrieved memories."""
    logger.info(f"✅ Found {len(memories)} relevant memories in {memory_query_time:.3f}s")
    
    for i, m in enumerate(memories, 1):
        similarity = m.get('similarity', 0.0)
        source_preview = m.get('source_text', '')[:60] + "..." if len(m.get('source_text', '')) > 60 else m.get('source_text', '')
        translation_preview = m.get('translation_text', '')[:60] + "..." if len(m.get('translation_text', '')) > 60 else m.get('translation_text', '')
        logger.info(f"  📝 Memory {i}: similarity={similarity:.3f}")
        logger.debug(f"    Source: {source_preview}")
        logger.debug(f"    Translation: {translation_preview}")
    
    similarities = [m.get('similarity', 0.0) for m in memories]
    avg_similarity = sum(similarities) / len(similarities) if similarities else 0
    max_similarity = max(similarities) if similarities else 0
    min_similarity = min(similarities) if similarities else 0
    
    logger.info(f"📊 Memory stats: avg_sim={avg_similarity:.3f}, max_sim={max_similarity:.3f}, min_sim={min_similarity:.3f}")
    logger.info(f"🔄 Memory context will be provided via system prompt, not user message")

def append_article_content_if_needed(source_message_text, message_entity_urls, flow_collector):
    """Extract and append article content to source message, creating enriched input for translation."""
    enriched_input = source_message_text
    
    if message_entity_urls and len(message_entity_urls) > 0:
        article_text = extract_article(message_entity_urls[0])
        if article_text:
            enriched_input += f"\n\nArticle content from {message_entity_urls[0]}:\n{article_text}"
            logger.info(f"Added article content ({len(article_text)} chars) to translation input")
            if flow_collector:
                flow_collector.log_article_extraction(message_entity_urls[0], article_text, True)
        else:
            enriched_input += f"\n\nNote: This message contains a link: {message_entity_urls[0]}"
            logger.info("Article extraction failed, using fallback link mention")
            if flow_collector:
                flow_collector.log_article_extraction(message_entity_urls[0], None, False)
    
    return enriched_input

async def perform_translation(enriched_input, memories, flow_collector):
    """Perform the actual translation using AutoGen system."""
    logger.info("Translating in modern Lurkmore style for Israeli Russian audience with editorial system...")
    translation_start = time.time()
    
    if flow_collector:
        memory_count = len(memories) if memories else 0
        flow_collector.log_autogen_start(enriched_input, memory_count)
    
    final_translation_text, conversation_log = await translate_and_link(enriched_input, memories, flow_collector)
    translation_time_ms = int((time.time() - translation_start) * 1000)
    
    if flow_collector:
        translation_time_seconds = translation_time_ms / 1000
        flow_collector.log_autogen_result(final_translation_text, conversation_log, translation_time_seconds)
    
    return final_translation_text, conversation_log

def format_final_content(final_translation_text, source_footer, message_entity_urls):
    """Format the final content with invisible links and footers."""
    logger.info("Safety check disabled - posting Lurkmore-style translation with navigation links")
    
    invisible_article_link = ""
    if message_entity_urls and len(message_entity_urls) > 0:
        invisible_article_link = f"[\u200B]({message_entity_urls[0]})"
        logger.info(f"Added invisible article link for thumbnail: {message_entity_urls[0]}")
    
    final_post_content = f"{invisible_article_link}{final_translation_text}{source_footer}"
    logger.info(f"📝 Final post content preview: {final_post_content[:200]}...")
    
    return final_post_content

async def send_translated_message(client_instance, dst_channel_to_use, final_post_content, flow_collector):
    """Send the translated message and return sent message object."""
    if flow_collector:
        flow_collector.log_final_content(final_post_content)
    
    sent_message = await client_instance.send_message(dst_channel_to_use, final_post_content, parse_mode='md')
    logger.info(f"Posted modern Lurkmore style version")
    
    return sent_message

def save_translation_to_memory(source_message_text, final_translation_text, conversation_log, message_id, sent_message, dst_channel_to_use):
    """Save the translation pair to memory storage."""
    save_start_time = time.time()
    try:
        pair_id = f"{message_id}-right" if message_id else str(uuid.uuid4())
        logger.info(f"💾 Saving translation pair to memory: {pair_id}")
        logger.debug(f"📝 Source length: {len(source_message_text)} chars, Translation length: {len(final_translation_text)} chars")
        
        destination_message_url = None
        if sent_message and hasattr(sent_message, 'id'):
            dest_channel_clean = dst_channel_to_use.replace("@", "")
            destination_message_url = f"https://t.me/{dest_channel_clean}/{sent_message.id}"
            logger.info(f"🔗 Constructed destination URL: {destination_message_url}")
        
        save_pair(
            source_message_text=source_message_text,
            tgt=final_translation_text,
            pair_id=pair_id,
            message_id=sent_message.id if sent_message else message_id,
            channel_name=dst_channel_to_use.replace("@", ""),
            message_url=destination_message_url,
            conversation_log=conversation_log,
        )
        save_time = time.time() - save_start_time
        logger.info(f"✅ Translation pair saved successfully in {save_time:.3f}s: {pair_id}")
        
    except Exception as e:
        save_time = time.time() - save_start_time
        logger.error(f"💥 TM save failed for {pair_id} after {save_time:.3f}s: {e}", exc_info=True)

async def translate_and_post(client_instance, source_message_text, message_id=None, destination_channel=None, message_entity_urls=None, flow_collector=None):
    """Main translation and posting flow - orchestrates the complete process."""
    try:
        start_time = initialize_translation_session(message_id, source_message_text, flow_collector)
        
        dst_channel_to_use, source_footer = determine_destination_channel_and_links(destination_channel, message_id)
        
        memories = query_translation_memory(source_message_text, message_id, flow_collector)
        
        enriched_input = append_article_content_if_needed(source_message_text, message_entity_urls, flow_collector)
        
        final_translation_text, conversation_log = await perform_translation(enriched_input, memories, flow_collector)
        
        final_post_content = format_final_content(final_translation_text, source_footer, message_entity_urls)
        
        sent_message = await send_translated_message(client_instance, dst_channel_to_use, final_post_content, flow_collector)
        
        save_translation_to_memory(source_message_text, final_translation_text, conversation_log, message_id, sent_message, dst_channel_to_use)
        
        logger.info(f"Total processing time for message: {time.time() - start_time:.2f} seconds")
        
        return sent_message
        
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}", exc_info=True)
        return False

def extract_message_urls(message):
    """Extract URLs from message entities."""
    message_entity_urls = []
    if hasattr(message, 'entities') and message.entities:
        for entity in message.entities:
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
                    url_text = message.text[entity.offset:entity.offset + entity.length]
                    if url_text.startswith('http'):
                        message_entity_urls.append(url_text)
                        logger.info(f"Extracted URL from text: {url_text}")
                    else:
                        logger.info(f"Found URL-like entity but not a valid URL: {url_text}")
    return message_entity_urls

async def process_message(client, message, destination_channel=None):
    """Simple unified message processing."""
    message_entity_urls = extract_message_urls(message)
    logger.info(f"Extracted URLs from message: {message_entity_urls}")
    await translate_and_post(        client, 
        message.text, 
        message.id, 
        destination_channel=destination_channel,
        message_entity_urls=message_entity_urls
    )

async def setup_event_handlers(client_instance):
    # Renamed client to client_instance
    @client_instance.on(events.NewMessage(chats=SRC_CHANNEL))
    async def handle_new_message(event):
        try:
            source_message_text = event.message.message
            if not source_message_text: return
            logger.info(f"Processing new message ID {event.message.id}: {source_message_text[:50]}...")
            
            await process_message(client_instance, event.message)
            logger.info(f"Successfully processed and posted message ID {event.message.id}")
        except Exception as e:
            logger.error(f"Error in handle_new_message: {str(e)}", exc_info=True)

async def process_recent_posts(client_instance, limit=None, timeout=None):
    # Renamed client to client_instance
    # Get processing limits from database
    processing_limits = config.get_processing_limits()
    if limit is None:
        limit = processing_limits['batch_message_limit']
    if timeout is None:
        timeout = processing_limits['batch_timeout_seconds']
    
    try:
        logger.info(f"Begin processing {limit} most recent posts from channel '{SRC_CHANNEL}'")
        start_time = time.time()
        fetch_timeout = min(processing_limits['fetch_timeout_seconds'], timeout / 2)
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
            if time.time() - start_time > timeout - processing_limits['timeout_buffer_seconds']: # Reserve time buffer
                logger.warning("Approaching timeout, stopping batch processing.")
                break
            logger.info(f"Processing message {msg.id}: {msg.text[:50]}...")
            
            try:
                await process_message(client_instance, msg)
                processed_count += 1
            except Exception as e:
                logger.error(f"Error processing message {msg.id}: {str(e)}", exc_info=True)
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
            
            logger.info(f"Processing message ID: {msg.id}")
            await process_message(client, msg)
            
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
    parser.add_argument('--translate-message', type=int, help='Translate a specific message ID from the source channel')
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
                # Get test mode limits from database
                test_batch_limit = int(await config.aget_setting('TEST_MODE_BATCH_LIMIT'))
                test_timeout = int(await config.aget_setting('TEST_MODE_TIMEOUT'))
                await process_recent_posts(client, limit=test_batch_limit, timeout=test_timeout)
            except Exception as e:
                logger.warning(f"TEST_MODE pre-processing recent posts failed: {e}")
        
        # Translate specific message if requested
        if args.translate_message:
            logger.info(f"Translating specific message ID: {args.translate_message}")
            try:
                # Get the specific message by ID
                messages = await client.get_messages(SRC_CHANNEL, ids=args.translate_message)
                if not messages:
                    logger.error(f"Message ID {args.translate_message} not found in channel {SRC_CHANNEL}")
                    return
                
                msg = messages[0] if isinstance(messages, list) else messages
                if not msg.text:
                    logger.error(f"Message ID {args.translate_message} has no text content")
                    return
                
                logger.info(f"Found message: {msg.text[:100]}...")
                
                await process_message(client, msg)
                logger.info(f"Successfully translated message ID {args.translate_message}")
                
            except Exception as e:
                logger.error(f"Failed to translate message ID {args.translate_message}: {e}", exc_info=True)
            
            logger.info("🏁 Exiting after translating specific message (not starting polling mode)")
            await client.disconnect()  # Properly disconnect client to prevent hanging
            return  # Exit after translating specific message
        
        # Process recent messages if requested
        if args.process_recent and args.process_recent > 0:
            logger.info(f"Processing {args.process_recent} recent messages")
            messages = await client.get_messages(SRC_CHANNEL, limit=args.process_recent)
            
            # Process each message
            for msg in reversed(messages):
                logger.info(f"Processing message ID: {msg.id}")
                if not msg.text: 
                    continue
                
                await process_message(client, msg)
            
            logger.info("Finished processing recent messages")
            logger.info("🏁 Exiting after processing recent messages (not starting polling mode)")
            await client.disconnect()  # Properly disconnect client to prevent hanging
            return  # Exit after processing recent messages, don't start polling
        
        logger.info(f"Client ready, listening for new messages on: {SRC_CHANNEL}")
        await client.run_until_disconnected()
        
    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 