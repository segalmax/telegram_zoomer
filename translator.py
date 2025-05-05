"""
Shared translation functionality for the Telegram Zoomer Bot
"""

import os
import logging
import openai
import time
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log

logger = logging.getLogger(__name__)

# Initialize OpenAI client - will use the OPENAI_API_KEY from environment
def get_openai_client(api_key):
    """Initialize the OpenAI client with the given API key"""
    logger.info("Initializing OpenAI client")
    return openai.OpenAI(api_key=api_key)

def get_prompt(style):
    """Get the appropriate prompt based on translation style"""
    logger.info(f"Getting prompt for style: {style}")
    if style == 'left':
        prompt = (
            "You are a razor-sharp Russian Gen Z activist with biting wit. "
            "Rewrite this news entirely in Russian, using edgy, punchy zoomer slang with savage humor—no English allowed, only Russian loanwords with Russian endings. "
            "Include one darkly funny punchline, use slang like 'криндж', 'лол', 'трушно', 'прикол', and emojis 🤯🔥. "
            "Keep the social justice angle but make it sound like a stand-up bit—zero fluff, zero formal tone!"
        )
        logger.info("Using LEFT style prompt")
        return prompt
    elif style == 'right':
        prompt = (
            "You are an unfiltered Russian Gen Z 'bidlo' armed with savage sarcasm. "
            "Rewrite the news entirely in Russian, using coarse, blunt bidlo slang—no English sentences whatsoever, only Russian loanwords. "
            "Deliver one gut-punch barb that drips disdain, use words like 'хуяк', 'патриот', 'бабки', and emojis 💀🤑. "
            "Crush leftist squeals, but keep the facts intact—full venom, zero vanilla."
        )
        logger.info("Using RIGHT style prompt")
        return prompt
    else:
        prompt = (
            "You are a Zoomer. Translate the following text into concise, punchy Russian Zoomer slang."
        )
        logger.info("Using DEFAULT style prompt")
        return prompt

@retry(
    stop=stop_after_attempt(3), 
    wait=wait_exponential(multiplier=1, min=4, max=10),
    before_sleep=before_sleep_log(logger, logging.WARNING)
)
async def translate_text(client, text, style='left'):
    """Translate text with exponential backoff retry logic"""
    try:
        start_time = time.time()
        logger.info(f"Starting translation for {len(text)} characters of text using style: {style}")
        
        # Get the appropriate prompt
        prompt = get_prompt(style)
        logger.info(f"Prompt length: {len(prompt)} characters")
        
        # Truncate text if it's extremely long for logging
        log_text = text[:100] + "..." if len(text) > 100 else text
        logger.info(f"Text to translate (truncated): {log_text}")
        
        # Make the API call
        logger.info(f"Sending request to OpenAI API using model: gpt-4o")
        api_start = time.time()
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text}
            ],
            max_completion_tokens=800,
            temperature=1
        )
        api_time = time.time() - api_start
        logger.info(f"OpenAI API call completed in {api_time:.2f} seconds")
        
        # Extract and return the result
        result = resp.choices[0].message.content.strip()
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
        logger.error(f"OpenAI API error: {str(e)}", exc_info=True)
        logger.error(f"Failed to translate text of length {len(text)}")
        raise 