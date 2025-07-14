"""Compatibility wrapper that exposes translate_and_link functions.
Legacy code replaced by AutoGen pipeline (see app.autogen_translation).
"""

from __future__ import annotations

import anthropic  # compatibility

from typing import Dict, Any, List

from app.autogen_translation import translate_and_link, translate_and_link_streaming  # noqa: F401 re-export
from app.config_loader import get_config_loader

config = get_config_loader()

# ---------------------------------------------------------------------------
# memory_block & make_linking_prompt are still referenced elsewhere (tests, etc.)
# Keep their original implementation but delegate to current config.
# ---------------------------------------------------------------------------

def memory_block(mem: List[Dict[str, Any]], k: int | None = None) -> str:  # noqa: D401
    """Return numbered summaries of previous translations for anti-repetition."""
    if k is None:
        k = int(config.get_setting('DEFAULT_RECALL_K'))
    max_chars = int(config.get_setting('MEMORY_SUMMARY_MAX_CHARS'))
    block = []
    for i, m in enumerate(mem[:k], 1):
        summary = (m['translation_text'].split('.')[0])[:max_chars].strip()
        block.append(f"{i}. {summary} → {m['message_url']}")
    return "\n".join(block)

def make_linking_prompt(mem: List[Dict[str, Any]]):
    monolithic_prompt = config.get_prompt('lurkmore_complete_original_prompt')
    memory_context = memory_block(mem) if mem else "Нет предыдущих постов."
    return monolithic_prompt.format(memory_list=memory_context)


def get_anthropic_client(api_key: str):  # noqa: D401
    """Legacy helper retained for bot import compatibility."""
    return anthropic.Anthropic(api_key=api_key)

 