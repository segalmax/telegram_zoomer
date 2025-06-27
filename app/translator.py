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

def get_prompt():
    """Get the prompt for right-bidlo translation style (only style supported)"""
    logger.info("Using RIGHT-BIDLO style prompt")
    prompt = (
        "Ты пишешь для русскоязычного Telegram-канала который ненавидит политкорректность, где читатели получают новости в хронологическом порядке. "
        "Твоя задача — дать честный, ироничный комментарий к происходящему, но каждый пост должен звучать естественно и по-разному.\n\n"
        
        "КРИТИЧЕСКИ ВАЖНО: Каждый абзац должен быть не длиннее 180 слов. "
        "Разбей текст на ясные, логичные абзацы (обычно 1–3), каждый из 2–3 предложений. "
        "Избегай длинных цитат, подзаголовков и лишних деталей. Если текст всё ещё слишком длинный, сократи менее важную информацию. "
        "Сохраняй ударность и лаконичность.\n\n"
        
        "ВАЖНО: Избегай повторения фраз и конструкций из предыдущих переводов. Ты видишь предыдущиe переводов — "
        "НЕ копируй их стиль дословно. Вместо шаблонных зачинов, находи свежие способы выражения.\n\n"
        "Если ты уже использовал какие-то оригинальные фразы в прошлых переводах, не повторяй их в этом переводе, иначе это не будет оригинально."
        
        "Адаптируй тон под тип новости:\n"
        "• Экстренные сводки — сухо, фактично, с едкими замечаниями\n"
        "• Политические разборки — цинично, но без истерики\n"
        "• Человеческие драмы — с пониманием, но без сентиментальности\n"
        "• Технические/научные темы — объясни суть, добавь контекст\n"
        "• Экономические вопросы — покажи, как это отразится на людях\n\n"
        
        "Пиши как умный циник, который:\n"
        "- Понимает механику власти и пропаганды\n"
        "- Видит связи между событиями\n"
        "- Не дает себя наебать красивыми словами\n"
        "- Может объяснить сложное простым языком\n"
        "- Использует разнообразную лексику (не только мат и сленг)\n\n"
        
        "Фокусируйся на:\n"
        "- Мотивах участников (например,кому это выгодно?)\n"
        "- Реальных последствиях для обычных людей\n"
        "- Исторических параллелях, когда уместно\n"
        "- Экономической/политической подоплеке\n\n"
        
        "Если в сообщении есть содержание статьи, используй его для контекста и точности перевода. "
        "Сосредоточься на основных фактах, а не только на заголовке.\n\n"
        
        "Не включай ссылки — они добавляются отдельно."
    )
    return prompt

@retry(
    stop=stop_after_attempt(3), 
    wait=wait_exponential(multiplier=1, min=4, max=10),
    before_sleep=before_sleep_log(logger, logging.WARNING)
)
async def translate_text(client, text):
    """Translate text using Claude Sonnet 4 with exponential backoff retry logic"""
    try:
        start_time = time.time()
        logger.info(f"Starting translation for {len(text)} characters of text")
        
        # Get the prompt (always right-bidlo style)
        prompt = get_prompt()
        logger.info(f"Prompt length: {len(prompt)} characters")
        
        # Truncate text if it's extremely long for logging
        log_text = text[:100] + "..." if len(text) > 100 else text
        logger.info(f"Text to translate (truncated): {log_text}")
        
        # Make the API call to Claude Sonnet 4
        logger.info(f"Sending request to Anthropic API using model: claude-sonnet-4-20250514")
        api_start = time.time()
        resp = client.messages.create(
            model="claude-sonnet-4-20250514",  # Using latest Claude Sonnet 4
            max_tokens=1000,
            temperature=0.85,  # Higher temperature for more creative and daring output
            system=prompt,
            messages=[
                {"role": "user", "content": text}
            ]
        )
        api_time = time.time() - api_start
        logger.info(f"Anthropic API call completed in {api_time:.2f} seconds")
        
        # Extract and return the result
        result = resp.content[0].text.strip()
        total_time = time.time() - start_time
        
        result_snippet = result[:100] + "..." if len(result) > 100 else result
        logger.info(f"Translation result (truncated): {result_snippet}")
        logger.info(f"Translation completed in {total_time:.2f} seconds")
        
        # Validate result contains Russian characters
        has_russian = any(ord('а') <= ord(c) <= ord('я') or ord('А') <= ord(c) <= ord('Я') for c in result)
        if not has_russian:
            logger.warning("Translation result doesn't contain Russian characters!")
        
        return result
    except Exception as e:
        logger.error(f"Anthropic API error: {str(e)}", exc_info=True)
        logger.error(f"Failed to translate text of length {len(text)}")
        raise 

async def safety_check_translation(client, translated_text):
    """
    Perform a safety check on the translated text to determine if it's appropriate to post.
    Returns True if safe to post, False if should be skipped.
    """
    try:
        logger.info("Performing safety check on translated content")
        
        safety_prompt = (
            "You are a content moderation assistant. Review the following Russian text and determine if it's appropriate to post on a public Telegram channel.\n\n"
            "Check for:\n"
            "1. Refusal text (like 'I cannot help with that' or similar)\n"
            "2. Inappropriate content for public posting\n"
            "3. Overly sensitive or offensive material\n"
            "4. Content that might violate platform guidelines\n\n"
            "Respond with ONLY 'SAFE' if the content is appropriate to post, or 'UNSAFE' if it should not be posted.\n"
            "Do not provide any explanation, just the single word response."
        )
        
        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=10,  # Very short response needed
            temperature=0.1,  # Low temperature for consistent safety decisions
            system=safety_prompt,
            messages=[
                {"role": "user", "content": translated_text}
            ]
        )
        
        safety_result = resp.content[0].text.strip().upper()
        logger.info(f"Safety check result: {safety_result}")
        
        is_safe = safety_result == "SAFE"
        if not is_safe:
            logger.warning(f"Translation failed safety check: {safety_result}")
        
        return is_safe
        
    except Exception as e:
        logger.error(f"Error during safety check: {str(e)}", exc_info=True)
        # If safety check fails, err on the side of caution and don't post
        logger.warning("Safety check failed, skipping post as precaution")
        return False 