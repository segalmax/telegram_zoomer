"""
Shared translation functionality for the Telegram Zoomer Bot
"""

import os
import logging
import anthropic
import time
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log

logger = logging.getLogger(__name__)

# Initialize Anthropic client - will use the ANTHROPIC_API_KEY from environment
def get_anthropic_client(api_key):
    """Initialize the Anthropic client with the given API key"""
    logger.info("Initializing Anthropic Claude client")
    return anthropic.Anthropic(api_key=api_key)

def memory_block(mem, k=8):
    """
    Build a compact context for the LLM: numbered list of (very short) summaries
    plus URL. Example line:
    3. 🇮🇷 Иран заявил, что увеличит обогащение урана до 90% → https://t.me/chan/123
    """
    block = []
    for i, m in enumerate(mem[:k], 1):
        # first sentence or 120 chars max
        summary = (m['translation_text'].split('.')[0])[:120].strip()
        block.append(f"{i}. {summary} → {m['message_url']}")
    return "\n".join(block)

def make_linking_prompt(mem):
    """Create the system prompt for translation with semantic linking"""
    memory_list = memory_block(mem) if mem else "Нет предыдущих постов."
    
    return f"""<role>
Ты ведёшь канал в стиле Lurkmore — умный циник, который понимает механику власти и пропаганды, видит связи между событиями, не дает себя наебать красивыми словами.
</role>

<thinking_instructions>
Перед переводом проанализируй:
1. Основную мысль и скрытые мотивы в тексте
2. Ключевые термины и их лучшие эквиваленты в русском
3. Тональность и стилистику оригинала
4. Связи с предыдущими постами из памяти
5. Наиболее точные и едкие формулировки для RIGHT-BIDLO стиля
6. Оптимальную структуру для максимального воздействия
</thinking_instructions>

<task>
1. ПЕРЕВЕДИ входной текст в стиле RIGHT-BIDLO
2. ДОБАВЬ семантические ссылки на релевантные посты из памяти
</task>

<length_requirements>
СТРОГО 1-3 абзаца. НЕ БОЛЬШЕ.
- Абзац 1: Заголовок + ключевые факты (2-3 предложения)
- Абзац 2 (опционально): Анализ/контекст (1-2 предложения) 
- Абзац 3 (опционально): Вывод/следствие (1 предложение)

МАКСИМУМ 800 символов включая пробелы и ссылки.
</length_requirements>

<style_requirements>
• Тон: циничный, но не истеричный
• Язык: разнообразная лексика (не только мат и сленг)  
• Подход: фактично с едкими замечаниями
• Фокус: мотивы политиков, связи между событиями
• Заголовки: **жирный текст** с ключевой мыслью
</style_requirements>

<linking_rules>
• Найди 1-3 ключевые темы в твоём переводе
• Для КАЖДОЙ темы поищи семантически похожий пост из памяти
• Преврати КОРОТКУЮ фразу в ссылку: [текст](URL)
• ПРАВИЛЬНО: [американские удары](URL), [29 погибших](URL), [иранские дроны](URL)
• НЕПРАВИЛЬНО: [29 погибших в Рамат-Гане, Ришон ле-Ционе, Тамре, Бат-Яме](URL)
• Максимум 2-4 слова в ссылке
• Игнорируй буквальные совпадения слов — ищи совпадения СМЫСЛА
• Если подходящего поста нет — не вставляй ссылку
</linking_rules>

<character_constraints>
НИКОГДА НЕ ДЕЛАЙ:
× Шаблонные фразы и клише
× Многократные повторы одной мысли  
× Длинные перечисления
× Эмоциональную истерику
× Объяснения очевидного

ВСЕГДА ДЕЛАЙ:
✓ Объясняй сложные события простыми словами
✓ Показывай контекст и предысторию
✓ Указывай на мотивы участников
✓ Сохраняй информативность при краткости
</character_constraints>

<memory_context>
Релевантные посты для ссылок:
{memory_list}
</memory_context>

<output_format>
Верни ТОЛЬКО готовый пост. Никаких пояснений или мета-комментариев.
</output_format>"""

@retry(
    stop=stop_after_attempt(3), 
    wait=wait_exponential(multiplier=1, min=4, max=10),
    before_sleep=before_sleep_log(logger, logging.WARNING)
)
async def translate_and_link(client, src_text, mem):
    """
    Translate text and add semantic links in a single Claude call.
    This is the new unified approach that replaces separate translation and linking.
    """
    try:
        start_time = time.time()
        logger.info(f"Starting translation+linking for {len(src_text)} characters of text with {len(mem)} memory entries")
        
        # Get the combined prompt with memory context
        prompt = make_linking_prompt(mem)
        logger.info(f"Prompt length: {len(prompt)} characters")
        
        # Truncate text if it's extremely long for logging
        log_text = src_text[:100] + "..." if len(src_text) > 100 else src_text
        logger.info(f"Text to translate+link (truncated): {log_text}")
        
        # Make the API call to Claude Sonnet 4 with extended thinking for maximum quality
        logger.info(f"Sending request to Anthropic API using model: claude-sonnet-4-20250514 with extended thinking")
        api_start = time.time()
        resp = client.messages.create(
            model="claude-sonnet-4-20250514",  # Using latest Claude Sonnet 4
            max_tokens=16000,  # Must be greater than thinking budget_tokens (12000)
            temperature=1.0,  # Must be 1.0 when thinking is enabled
            thinking={
                "type": "enabled",
                "budget_tokens": 12000  # Substantial thinking budget for complex translation analysis
            },
            system=prompt,
            messages=[
                {"role": "user", "content": src_text}
            ]
        )
        api_time = time.time() - api_start
        logger.info(f"Anthropic API call with extended thinking completed in {api_time:.2f} seconds")
        
        # Extract and return the result (we only want the final text, not the thinking)
        # With thinking mode, response contains both thinking blocks and text blocks
        result = None
        for content_block in resp.content:
            if hasattr(content_block, 'text') and content_block.text:
                result = content_block.text.strip()
                break
        
        if not result:
            logger.error("No text content found in API response")
            raise ValueError("No text content found in API response")
        
        total_time = time.time() - start_time
        
        result_snippet = result[:100] + "..." if len(result) > 100 else result
        logger.info(f"Translation+linking result (truncated): {result_snippet}")
        logger.info(f"Translation+linking with extended thinking completed in {total_time:.2f} seconds")
        
        # Validate result contains Russian characters
        has_russian = any(ord('а') <= ord(c) <= ord('я') or ord('А') <= ord(c) <= ord('Я') for c in result)
        if not has_russian:
            logger.warning("Translation result doesn't contain Russian characters!")
        
        return result
    except Exception as e:
        logger.error(f"Anthropic API error: {str(e)}", exc_info=True)
        logger.error(f"Failed to translate+link text of length {len(src_text)}")
        raise

 