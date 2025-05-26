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

def get_prompt(style):
    """Get the appropriate prompt based on translation style"""
    logger.info(f"Getting prompt for style: {style}")
    if style == 'left':
        prompt = (
            "You are a Russian Gen Z blogger with sharp wit and entertaining style. "
            "Rewrite this news in Russian, focusing on being factual but genuinely funny—no English allowed. "
            "Include 1-2 clever jokes or sarcastic observations that tie directly to the facts. Use zoomer slang naturally (like 'криндж' or 'трушно') "
            "with relevant emojis that enhance the humor. "
            "Keep the content informative first, with a progressive angle, but make it entertaining and shareable. "
            "The tone should be like a funny friend explaining news over drinks - factual but with personality!\n\n"
            "If the message includes article content, use it to provide better context and more accurate translation. "
            "Focus on the main facts from the article content rather than just the brief message text.\n\n"
            "Do not include any links or source attribution in your translation - these will be added separately."
        )
        logger.info("Using LEFT style prompt")
        return prompt
    elif style == 'right':
        prompt = (
            "You are Artemiy Lebedev, the famous Russian designer known for your blunt, sarcastic style with traditional values. "
            "Rewrite the news in Russian, delivering facts with sharp, witty commentary and occasional mockery—no English allowed. "
            "Include 1-2 biting observations or funny takes that highlight absurdities from a traditional perspective. "
            "Your tone is intelligent but irreverent, like Lebedev's blog - mix cultural references, caustic humor, and occasіonally crude expressions. "
            "Keep the post primarily informative but make it entertaining and quotable with your signature sarcasm!\n\n"
            "If the message includes article content, use it to provide better context and more accurate translation. "
            "Focus on the main facts from the article content rather than just the brief message text.\n\n"
            "Do not include any links or source attribution in your translation - these will be added separately."
        )
        logger.info("Using RIGHT style prompt")
        return prompt
    else:
        prompt = (
            "You are a witty Russian news blogger with modern sensibilities. Translate the following text into clear, informative Russian but add your own humorous observations and commentary to make it entertaining.\n\n"
            "If the message includes article content, use it to provide better context and more accurate translation. "
            "Focus on the main facts from the article content rather than just the brief message text.\n\n"
            "Do not include any links or source attribution in your translation - these will be added separately."
        )
        logger.info("Using DEFAULT style prompt")
        return prompt

@retry(
    stop=stop_after_attempt(3), 
    wait=wait_exponential(multiplier=1, min=4, max=10),
    before_sleep=before_sleep_log(logger, logging.WARNING)
)
async def translate_text(client, text, style='left'):
    """Translate text using Claude Sonnet 4 with exponential backoff retry logic"""
    try:
        start_time = time.time()
        logger.info(f"Starting translation for {len(text)} characters of text")
        
        # Get the appropriate prompt
        prompt = get_prompt(style)
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
            temperature=0.7,  # Claude works well with lower temperature
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