"""
Shared translation functionality for the Telegram Zoomer Bot
"""

import os
import logging
import anthropic
import time
from asgiref.sync import sync_to_async
from app.config_loader import get_config_loader

logger = logging.getLogger(__name__)
config = get_config_loader()

# Initialize Anthropic client - will use the ANTHROPIC_API_KEY from environment
def get_anthropic_client(api_key):
    """Initialize the Anthropic client with the given API key"""
    logger.info("Initializing Anthropic Claude client")
    return anthropic.Anthropic(api_key=api_key)

def call_claude_stream(client, system_prompt, user_message):
    """Claude API call with streaming and comprehensive debugging"""
    
    import time
    
    # Get AI model configuration from database
    ai_config = config.get_ai_model_config()
    
    # Start timing
    start_time = time.time()
    print(f"🧠 {ai_config['model_id']} thinking...")
    
    # Use streaming with comprehensive debugging
    with client.messages.stream(
        model=ai_config['model_id'],
        max_tokens=ai_config['max_tokens'],
        temperature=ai_config['temperature'],
        thinking={
            "type": "enabled",
            "budget_tokens": ai_config['thinking_budget_tokens']
        },
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_message}
        ]
    ) as stream:
        
        # Initialize tracking variables
        full_response = ""
        thinking_content = ""
        thinking_started = False
        text_started = False
        
        # Token usage tracking
        input_tokens = 0
        output_tokens = 0
        thinking_tokens = 0
        cache_read_tokens = 0
        cache_write_tokens = 0
        
        # Process all stream events
        for event in stream:
            if hasattr(event, 'type'):
                event_type = event.type
                
                # Handle thinking content start
                if event_type == "content_block_start" and hasattr(event, 'content_block') and getattr(event.content_block, 'type', None) == 'thinking':
                    if not thinking_started:
                        print(f"\n")  # Just a line break
                        thinking_started = True
                
                # Handle streaming deltas
                elif event_type == "content_block_delta" and hasattr(event, 'delta'):
                    if hasattr(event.delta, 'type'):
                        delta_type = event.delta.type
                        
                        # Stream thinking content like Claude GUI
                        if delta_type == 'thinking_delta':
                            chunk_text = getattr(event.delta, 'thinking', '')
                            thinking_content += chunk_text
                            print(chunk_text, end='', flush=True)
                            
                        # Stream text content like Claude GUI  
                        elif delta_type == 'text_delta':
                            chunk_text = getattr(event.delta, 'text', '')
                            full_response += chunk_text
                            
                            if not text_started:
                                print(f"\n\n💬 Response:")
                                text_started = True
                            
                            print(chunk_text, end='', flush=True)
                
                # Track token usage from API events
                elif event_type == "message_start":
                    if hasattr(event, 'message') and hasattr(event.message, 'usage'):
                        usage = event.message.usage
                        input_tokens = getattr(usage, 'input_tokens', 0)
                        cache_read_tokens = getattr(usage, 'cache_read_input_tokens', 0)
                        cache_write_tokens = getattr(usage, 'cache_creation_input_tokens', 0)
                
                elif event_type == "message_delta":
                    if hasattr(event, 'usage'):
                        usage = event.usage
                        output_tokens += getattr(usage, 'output_tokens', 0)
                
                # Clean phase transitions
                elif event_type == "content_block_stop":
                    content_block = getattr(event, 'content_block', None)
                    block_type = getattr(content_block, 'type', 'unknown') if content_block else 'unknown'
                    if block_type == 'thinking':
                        print(f"\n")  # Just add a line break after thinking
                        # Estimate thinking tokens from content length
                        thinking_tokens = len(thinking_content.split())
            
            # Handle direct text streaming (fallback)
            elif hasattr(event, 'text'):
                chunk_text = event.text
                full_response += chunk_text
                if not text_started:
                    print(f"\n💬 Response:")
                    text_started = True
                print(chunk_text, end='', flush=True)
        
        # Calculate costs and display comprehensive stats
        end_time = time.time()
        duration = end_time - start_time
        
        # Get model pricing (2025 rates)
        model_id = ai_config['model_id']
        pricing = get_model_pricing(model_id)
        
        # Calculate costs in dollars
        input_cost = (input_tokens / 1_000_000) * pricing['input']
        output_cost = (output_tokens / 1_000_000) * pricing['output']
        cache_read_cost = (cache_read_tokens / 1_000_000) * pricing['cache_read']
        cache_write_cost = (cache_write_tokens / 1_000_000) * pricing['cache_write']
        total_cost = input_cost + output_cost + cache_read_cost + cache_write_cost
        
        # Display clean stats
        print(f"\n\n📊 Claude API Statistics")
        print(f"{'='*40}")
        print(f"⏱️  Duration: {duration:.1f}s")
        print(f"🎯 Model: {model_id}")
        
        # Token breakdown
        total_tokens = input_tokens + output_tokens
        print(f"\n📝 Token Usage:")
        if input_tokens > 0:
            print(f"   Input: {input_tokens:,} tokens (${input_cost:.4f})")
        if thinking_tokens > 0:
            print(f"   Thinking: ~{thinking_tokens:,} tokens (estimated)")
        if output_tokens > 0:
            print(f"   Output: {output_tokens:,} tokens (${output_cost:.4f})")
        if cache_read_tokens > 0:
            print(f"   Cache Read: {cache_read_tokens:,} tokens (${cache_read_cost:.4f})")
        if cache_write_tokens > 0:
            print(f"   Cache Write: {cache_write_tokens:,} tokens (${cache_write_cost:.4f})")
        print(f"   Total: {total_tokens:,} tokens")
        
        # Cost summary
        print(f"\n💰 Cost Breakdown:")
        print(f"   This call: ${total_cost:.4f}")
        if total_cost > 0:
            cost_per_1k_chars = (total_cost / len(full_response)) * 1000 if len(full_response) > 0 else 0
            print(f"   Per 1K chars: ${cost_per_1k_chars:.4f}")
        
        # Performance metrics
        print(f"\n⚡ Performance:")
        if len(full_response) > 0:
            print(f"   Response: {len(full_response):,} characters")
            print(f"   Speed: {len(full_response)/duration:.0f} chars/sec")
        if output_tokens > 0:
            print(f"   Generation: {output_tokens/duration:.0f} tokens/sec")

        print(f"🔚")
        
        return full_response


def get_model_pricing(model_id):
    """Get current 2025 pricing for Claude models (USD per million tokens)"""
    pricing_map = {
        # Claude 4 models
        'claude-4-opus-20250514': {
            'input': 15.00, 'output': 75.00, 'cache_read': 1.50, 'cache_write': 30.00
        },
        'claude-sonnet-4-20250514': {
            'input': 3.00, 'output': 15.00, 'cache_read': 0.30, 'cache_write': 6.00
        },
        
        # Claude 3.7 models
        'claude-3-7-sonnet-20241201': {
            'input': 3.00, 'output': 15.00, 'cache_read': 0.30, 'cache_write': 6.00
        },
        
        # Claude 3.5 models
        'claude-3-5-sonnet-20241201': {
            'input': 3.00, 'output': 15.00, 'cache_read': 0.30, 'cache_write': 6.00
        },
        'claude-3-5-haiku-20241022': {
            'input': 0.80, 'output': 4.00, 'cache_read': 0.08, 'cache_write': 1.60
        },
        
        # Claude 3 models
        'claude-3-opus-20240229': {
            'input': 15.00, 'output': 75.00, 'cache_read': 1.50, 'cache_write': 30.00
        },
        'claude-3-sonnet-20240229': {
            'input': 3.00, 'output': 15.00, 'cache_read': 0.30, 'cache_write': 6.00
        },
        'claude-3-haiku-20240307': {
            'input': 0.25, 'output': 1.25, 'cache_read': 0.03, 'cache_write': 0.50
        }
    }
    
    # Default to Sonnet 4 pricing if model not found
    return pricing_map.get(model_id, pricing_map['claude-sonnet-4-20250514'])

def memory_block(mem, k=None):
    """
    Build a compact context for the LLM: numbered list of (very short) summaries
    plus URL. Example line:
    3. 🇮🇷 Иран заявил, что увеличит обогащение урана до 90% → https://t.me/chan/123
    """
    if k is None:
        k = int(config.get_setting('DEFAULT_RECALL_K'))
    
    max_chars = int(config.get_setting('MEMORY_SUMMARY_MAX_CHARS'))
    
    block = []
    for i, m in enumerate(mem[:k], 1):
        # first sentence or max_chars max
        summary = (m['translation_text'].split('.')[0])[:max_chars].strip()
        block.append(f"{i}. {summary} → {m['message_url']}")
    return "\n".join(block)

def make_linking_prompt(mem):
    """Create the system prompt for translation with semantic linking"""
    # Use monolithic prompt system
    monolithic_prompt = config.get_prompt('lurkmore_complete_original_prompt')
    memory_context = memory_block(mem) if mem else "Нет предыдущих постов."
    return monolithic_prompt.format(memory_list=memory_context)

class LLMEditor:
    """Minimal LLM Editor for critiquing translations"""
    
    def __init__(self, client):
        self.client = client
        
    def critique_translation(self, translation_text, source_text, memory_context, translator_prompt):
        """Critique a translation for repetitions and quality against the exact translator instructions"""
        
        # Use editor critique prompt from database
        editor_prompt = config.get_prompt('lurkmore_editor_critique_prompt')
        
        prompt = editor_prompt.format(
            translator_prompt=translator_prompt,
            source_text=source_text,
            translation_text=translation_text,
            memory_context=memory_context
        )
        
        response = call_claude_stream(self.client, "", prompt)
        
        return response

def call_claude_stream_with_yield(client, system_prompt, user_message, step_name="Claude"):
    """Claude API call with streaming that yields thinking and response chunks for Streamlit"""
    
    import time
    
    # Get AI model configuration from database
    ai_config = config.get_ai_model_config()
    
    # Start timing
    start_time = time.time()
    
    # Use streaming with comprehensive debugging
    with client.messages.stream(
        model=ai_config['model_id'],
        max_tokens=ai_config['max_tokens'],
        temperature=ai_config['temperature'],
        thinking={
            "type": "enabled",
            "budget_tokens": ai_config['thinking_budget_tokens']
        },
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_message}
        ]
    ) as stream:
        
        # Initialize tracking variables
        full_response = ""
        thinking_content = ""
        thinking_started = False
        text_started = False
        
        # Token usage tracking
        input_tokens = 0
        output_tokens = 0
        thinking_tokens = 0
        cache_read_tokens = 0
        cache_write_tokens = 0
        
        # Yield status update
        yield {
            'type': 'status',
            'content': f'{step_name} is thinking...',
            'step_name': step_name
        }
        
        # Create generators for thinking and response
        thinking_chunks = []
        response_chunks = []
        
        # Process all stream events
        for event in stream:
            if hasattr(event, 'type'):
                event_type = event.type
                
                # Handle thinking content start
                if event_type == "content_block_start" and hasattr(event, 'content_block') and getattr(event.content_block, 'type', None) == 'thinking':
                    if not thinking_started:
                        thinking_started = True
                
                # Handle streaming deltas
                elif event_type == "content_block_delta" and hasattr(event, 'delta'):
                    if hasattr(event.delta, 'type'):
                        delta_type = event.delta.type
                        
                        # Stream thinking content like Claude GUI
                        if delta_type == 'thinking_delta':
                            chunk_text = getattr(event.delta, 'thinking', '')
                            thinking_content += chunk_text
                            thinking_chunks.append(chunk_text)
                            
                        # Stream text content like Claude GUI  
                        elif delta_type == 'text_delta':
                            chunk_text = getattr(event.delta, 'text', '')
                            full_response += chunk_text
                            response_chunks.append(chunk_text)
                            
                            if not text_started:
                                text_started = True
                
                # Track token usage from API events
                elif event_type == "message_start":
                    if hasattr(event, 'message') and hasattr(event.message, 'usage'):
                        usage = event.message.usage
                        input_tokens = getattr(usage, 'input_tokens', 0)
                        cache_read_tokens = getattr(usage, 'cache_read_input_tokens', 0)
                        cache_write_tokens = getattr(usage, 'cache_creation_input_tokens', 0)
                
                elif event_type == "message_delta":
                    if hasattr(event, 'usage'):
                        usage = event.usage
                        output_tokens += getattr(usage, 'output_tokens', 0)
                
                # Handle phase transitions
                elif event_type == "content_block_stop":
                    content_block = getattr(event, 'content_block', None)
                    block_type = getattr(content_block, 'type', 'unknown') if content_block else 'unknown'
                    
                    if block_type == 'thinking' and thinking_chunks:
                        # Yield thinking stream
                        yield {
                            'type': 'thinking',
                            'content': thinking_chunks,
                            'step_name': step_name
                        }
                        thinking_tokens = len(thinking_content.split())
        
        # Yield response stream if we have content
        if response_chunks:
            yield {
                'type': 'response',
                'content': response_chunks,
                'step_name': step_name
            }
        
        # Calculate final stats
        end_time = time.time()
        duration = end_time - start_time
        
        # Get model pricing (2025 rates)
        model_id = ai_config['model_id']
        pricing = get_model_pricing(model_id)
        
        # Calculate costs in dollars
        total_tokens = input_tokens + output_tokens
        input_cost = (input_tokens / 1_000_000) * pricing['input']
        output_cost = (output_tokens / 1_000_000) * pricing['output']
        cache_read_cost = (cache_read_tokens / 1_000_000) * pricing['cache_read']
        cache_write_cost = (cache_write_tokens / 1_000_000) * pricing['cache_write']
        total_cost = input_cost + output_cost + cache_read_cost + cache_write_cost
        
        # Yield final stats
        yield {
            'type': 'stats',
            'content': {
                'duration': duration,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'thinking_tokens': thinking_tokens,
                'total_cost': total_cost,
                'response_length': len(full_response)
            },
            'step_name': step_name
        }
        
        return full_response

async def translate_and_link(client, src_text, mem):
    """
    Translate text with editorial review system.
    Uses LLMTranslator + LLMEditor for SINGLE iteration quality refinement.
    
    CRITICAL FEATURE: Agentic editorial system with conversation logging (1 iteration to avoid timeouts)
    """
    try:
        start_time = time.time()
        logger.info(f"Starting editorial translation for {len(src_text)} characters with {len(mem)} memory entries")
        
        # Get max iterations from config using async wrapper - CRASH if it fails
        max_iters = int(await sync_to_async(config.get_setting)('MAX_ITERATIONS_EDITORIAL'))
            
        logger.info(f"Starting editorial conversation between translator and editor ({max_iters} iteration)")
        final_translation, conversation_log = await sync_to_async(editorial_process)(client, src_text, mem, max_iters)
        
        total_time = time.time() - start_time
        
        result_snippet = final_translation[:100] + "..." if len(final_translation) > 100 else final_translation
        logger.info(f"Editorial translation completed in {total_time:.2f} seconds: {result_snippet}")
        
        # Return both translation and conversation log
        return final_translation, conversation_log
        
    except Exception as e:
        logger.error(f"Editorial translation error: {str(e)}", exc_info=True)
        raise

async def translate_and_link_streaming(client, src_text, mem):
    """
    Streaming version of translate_and_link that yields real-time updates for Streamlit.
    Shows Claude's thinking process and responses as they happen.
    """
    try:
        start_time = time.time()
        logger.info(f"Starting streaming editorial translation for {len(src_text)} characters")
        
        # Get max iterations from config using async wrapper
        max_iters = int(await sync_to_async(config.get_setting)('MAX_ITERATIONS_EDITORIAL'))
        
        conversation_log = []
        
        # Prepare translator prompt and memory context
        translator_prompt = await sync_to_async(make_linking_prompt)(mem)
        
        # Get "no previous posts" text from database
        no_memory_text = await sync_to_async(config.get_setting)('NO_MEMORY_TEXT') 
        memory_context_str = await sync_to_async(memory_block)(mem) if mem else no_memory_text
        
        # Step 1: Initial translation
        yield {
            'type': 'status',
            'content': 'Starting initial translation...',
            'step_name': 'Translator'
        }
        
        # Stream initial translation
        current_translation = ""
        async for update in async_claude_stream_generator(client, translator_prompt, src_text, "Initial Translation"):
            yield update
            if update['type'] == 'response' and 'content' in update:
                # Accumulate response chunks
                if isinstance(update['content'], list):
                    current_translation += ''.join(update['content'])
                else:
                    current_translation = update['content']
        
        conversation_log.append(f"ПЕРЕВОД v1: {current_translation}")
        
        # Step 2: Editor critique (single iteration to avoid timeouts)
        for iteration in range(max_iters):
            yield {
                'type': 'status',
                'content': f'Editor is reviewing translation (iteration {iteration + 1})...',
                'step_name': 'Editor'
            }
            
            # Create editor critique
            editor_prompt = await sync_to_async(config.get_prompt)('lurkmore_editor_critique_prompt')
            
            critique_prompt = editor_prompt.format(
                translator_prompt=translator_prompt,
                source_text=src_text,
                translation_text=current_translation,
                memory_context=memory_context_str
            )
            
            # Stream editor critique
            critique = ""
            async for update in async_claude_stream_generator(client, "", critique_prompt, f"Editor Critique #{iteration + 1}"):
                yield update
                if update['type'] == 'response' and 'content' in update:
                    if isinstance(update['content'], list):
                        critique += ''.join(update['content'])
                    else:
                        critique = update['content']
            
            conversation_log.append(f"РЕДАКТОР (итерация {iteration + 1}): {critique}")
            
            # Step 3: Translator revision
            yield {
                'type': 'status',
                'content': f'Translator is revising based on feedback...',
                'step_name': 'Translator Revision'
            }
            
            # Create revision context message - just use the original translator system prompt
            # with the conversation history and critique as the user message
            revision_user_message = f"""ИТЕРАЦИЯ {iteration + 1} из {max_iters}

ПОЛНАЯ ИСТОРИЯ РАЗРАБОТКИ:
{chr(10).join(conversation_log)}

ИСХОДНЫЙ ТЕКСТ:
{src_text}

ТЕКУЩЕЕ СОСТОЯНИЕ:
Твой текущий перевод: {current_translation}

ПОСЛЕДНЯЯ КРИТИКА РЕДАКТОРА:
{critique}

ЗАДАЧА: 
1. Проанализируй всю историю диалога - что ты пробовал, что сработало, что нет
2. Пойми эволюцию своих переводов и логику критики редактора
3. Учти все предыдущие замечания и создай улучшенную версию
4. Покажи, что ты учишься на своих ошибках и развиваешь подход

Создай следующую версию перевода, которая решает выявленные проблемы."""
            
            # Stream translator revision using the same original translator prompt
            async for update in async_claude_stream_generator(client, translator_prompt, revision_user_message, f"Revised Translation v{iteration + 2}"):
                yield update
                if update['type'] == 'response' and 'content' in update:
                    if isinstance(update['content'], list):
                        current_translation = ''.join(update['content'])
                    else:
                        current_translation = update['content']
            
            conversation_log.append(f"ПЕРЕВОД v{iteration + 2}: {current_translation}")
        
        # Final completion
        total_time = time.time() - start_time
        full_conversation_log = "\n\n".join(conversation_log)
        
        yield {
            'type': 'complete',
            'final_translation': current_translation,
            'conversation_log': full_conversation_log,
            'duration': total_time,
            'step_name': 'Complete'
        }
        
        logger.info(f"Streaming editorial translation completed in {total_time:.2f} seconds")
        
    except Exception as e:
        logger.error(f"Streaming editorial translation error: {str(e)}", exc_info=True)
        yield {
            'type': 'error',
            'content': str(e),
            'step_name': 'Error'
        }

async def async_claude_stream_generator(client, system_prompt, user_message, step_name):
    """Async generator wrapper for Claude streaming"""
    
    # Convert sync generator to async
    sync_gen = call_claude_stream_with_yield(client, system_prompt, user_message, step_name)
    
    for update in sync_gen:
        yield update

def editorial_process(client, source_text, memory_list, max_iterations=None):
    """Run editorial conversation between translator and editor - SINGLE ITERATION to avoid timeouts"""
    
    if max_iterations is None:
        max_iterations = int(config.get_setting('MAX_ITERATIONS_EDITORIAL'))
    
    editor = LLMEditor(client)
    conversation_log = []
    
    # Initial translation
    translator_prompt = make_linking_prompt(memory_list)
    
    # Get "no previous posts" text from database
    no_memory_text = config.get_setting('NO_MEMORY_TEXT')
    memory_context_str = memory_block(memory_list) if memory_list else no_memory_text
    
    current_translation = call_claude_stream(client, translator_prompt, source_text)
    conversation_log.append(f"ПЕРЕВОД v1: {current_translation}")
    
    # Single editorial iteration to avoid token explosion
    for iteration in range(max_iterations):
        # Editor critique with full translator instructions
        critique = editor.critique_translation(current_translation, source_text, memory_context_str, translator_prompt)
        conversation_log.append(f"РЕДАКТОР (итерация {iteration + 1}): {critique}")
        
        # Create revision context message - just use the original translator system prompt
        # with the conversation history and critique as the user message  
        revision_user_message = f"""ИТЕРАЦИЯ {iteration + 1} из {max_iterations}

ПОЛНАЯ ИСТОРИЯ РАЗРАБОТКИ:
{chr(10).join(conversation_log)}

ИСХОДНЫЙ ТЕКСТ:
{source_text}

ТЕКУЩЕЕ СОСТОЯНИЕ:
Твой текущий перевод: {current_translation}

ПОСЛЕДНЯЯ КРИТИКА РЕДАКТОРА:
{critique}

ЗАДАЧА: 
1. Проанализируй всю историю диалога - что ты пробовал, что сработало, что нет
2. Пойми эволюцию своих переводов и логику критики редактора
3. Учти все предыдущие замечания и создай улучшенную версию
4. Покажи, что ты учишься на своих ошибках и развиваешь подход

Создай следующую версию перевода, которая решает выявленные проблемы."""
        
        # Use the same original translator prompt for revision
        current_translation = call_claude_stream(client, translator_prompt, revision_user_message)
        conversation_log.append(f"ПЕРЕВОД v{iteration + 2}: {current_translation}")
    
    return current_translation, "\n\n".join(conversation_log)

 