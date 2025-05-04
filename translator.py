"""
Shared translation functionality for the Telegram Zoomer Bot
"""

import os
import logging
import openai
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# Initialize OpenAI client - will use the OPENAI_API_KEY from environment
def get_openai_client(api_key):
    """Initialize the OpenAI client with the given API key"""
    return openai.OpenAI(api_key=api_key)

def get_prompt(style):
    """Get the appropriate prompt based on translation style"""
    if style == 'left':
        return (
            "You are a razor-sharp Russian Gen Z activist with biting wit. "
            "Rewrite this news entirely in Russian, using edgy, punchy zoomer slang with savage humor—no English allowed, only Russian loanwords with Russian endings. "
            "Include one darkly funny punchline, use slang like 'криндж', 'лол', 'трушно', 'прикол', and emojis 🤯🔥. "
            "Keep the social justice angle but make it sound like a stand-up bit—zero fluff, zero formal tone!"
        )
    elif style == 'right':
        return (
            "You are an unfiltered Russian Gen Z 'bidlo' armed with savage sarcasm. "
            "Rewrite the news entirely in Russian, using coarse, blunt bidlo slang—no English sentences whatsoever, only Russian loanwords. "
            "Deliver one gut-punch barb that drips disdain, use words like 'хуяк', 'патриот', 'бабки', and emojis 💀🤑. "
            "Crush leftist squeals, but keep the facts intact—full venom, zero vanilla."
        )
    else:
        return (
            "You are a Zoomer. Translate the following text into concise, punchy Russian Zoomer slang."
        )

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def translate_text(client, text, style='left'):
    """Translate text with exponential backoff retry logic"""
    try:
        prompt = get_prompt(style)
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
    except Exception as e:
        logger.error(f"OpenAI API error: {str(e)}")
        raise 