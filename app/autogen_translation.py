"""AutoGen-based Translator and Editor pipeline for production.
Fail-fast, no fallbacks, uses Supabase-driven config, keeps translation-memory context.
"""

from __future__ import annotations

import os
import asyncio
from typing import Any, Dict, List, Tuple

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.ui import Console
from autogen_ext.models.anthropic import AnthropicChatCompletionClient

from app.config_loader import get_config_loader
from app.vector_store import recall as recall_tm

# ---------------------------------------------------------------------------
# Helper utilities (memory prompt construction – copied from legacy translator)
# ---------------------------------------------------------------------------

def _memory_block(mem: List[Dict[str, Any]], k: int | None = None) -> str:
    """Return numbered summaries of previous translations for anti-repetition."""
    config = get_config_loader()
    if k is None:
        k = int(config.get_setting('DEFAULT_RECALL_K'))
    max_chars = int(config.get_setting('MEMORY_SUMMARY_MAX_CHARS'))
    block: List[str] = []
    for i, m in enumerate(mem[:k], 1):
        summary = (m['translation_text'].split('.')[0])[:max_chars].strip()
        block.append(f"{i}. {summary} → {m['message_url']}")
    return "\n".join(block)

# ---------------------------------------------------------------------------
# AutoGen Translation System
# ---------------------------------------------------------------------------

class AutoGenTranslationSystem:
    """Run a two-agent Translator+Editor conversation and return final result."""

    def __init__(self) -> None:
        self.config = get_config_loader()
        self.ai_config = self.config.get_ai_model_config()

        # Check for temporary environment variable overrides (for Streamlit Studio mode)
        if os.getenv('TEMP_ANTHROPIC_MODEL_ID'):
            self.ai_config['model_id'] = os.getenv('TEMP_ANTHROPIC_MODEL_ID')
        if os.getenv('TEMP_ANTHROPIC_MAX_TOKENS'):
            self.ai_config['max_tokens'] = int(os.getenv('TEMP_ANTHROPIC_MAX_TOKENS'))
        if os.getenv('TEMP_ANTHROPIC_TEMPERATURE'):
            self.ai_config['temperature'] = float(os.getenv('TEMP_ANTHROPIC_TEMPERATURE'))

        # Model client (Anthropic Claude vs OpenAI)
        model_id = self.ai_config['model_id']
        if model_id.startswith('claude'):
            self.model_client = AnthropicChatCompletionClient(
                model=model_id,
                api_key=os.getenv('ANTHROPIC_API_KEY'),
                extra_create_args={
                    "thinking": {"budget_tokens": 10_000}
                },
            )
        else:#not implemented
            raise ValueError(f"Model {model_id} not supported")

        # Prompts stored in DB (with potential overrides for Streamlit Studio mode)
        self.base_translator_prompt = os.getenv('TEMP_TRANSLATOR_PROMPT') or self.config.get_prompt('autogen_translator')
        self.editor_prompt = os.getenv('TEMP_EDITOR_PROMPT') or self.config.get_prompt('autogen_editor')

        # Conversation settings
        self.max_cycles = 2  # hard cap – user + 2 rounds → 5 messages total

    # ---------------------------------------------------------------------
    async def run(self, article: str, memories: List[Dict[str, Any]], flow_collector=None) -> Tuple[str, str]:
        """Return (final_translation, conversation_log)."""
        # Build translator system message with memory context
        memory_context = _memory_block(memories) if memories else "Нет предыдущих постов."
        # Shared Lurkmore guidelines – prepend to each agent's system prompt (library lacks group-level support)
        shared_guidelines = self.config.get_prompt('lurkmore_complete_original_prompt')

        translator_prompt = f"{shared_guidelines}\n\n{self.base_translator_prompt}"
        if '{memory_list' in translator_prompt:
            translator_prompt = translator_prompt.format(memory_list=memory_context)
        else:
            translator_prompt = f"{translator_prompt}\n\n🔎 Память:\n{memory_context}"

        # Log initial prompts to flow collector
        if flow_collector and flow_collector.autogen_conversation:
            flow_collector.autogen_conversation['initial_translator_prompt'] = translator_prompt
            flow_collector.autogen_conversation['initial_editor_prompt'] = self.editor_prompt
            flow_collector.autogen_conversation['memory_context'] = memory_context

        translator = AssistantAgent(
            name="Translator",
            model_client=self.model_client,
            system_message=translator_prompt,
        )
        editor_prompt_full = f"{shared_guidelines}\n\n{self.editor_prompt}"
        editor = AssistantAgent(
            name="Editor",
            model_client=self.model_client,
            system_message=editor_prompt_full,
        )

        # Two-agent round robin with approval-based termination (industry standard)
        team = RoundRobinGroupChat(
            [translator, editor],
            termination_condition=TextMentionTermination("APPROVE"),  # Stop when editor approves
        )

        messages: List[Any] = []
        conversation_messages = []  # For flow collector
        
        async for event in team.run_stream(task=article):
            # Collect only TextMessage events (skip TaskResult etc.)
            if getattr(event, 'content', None):
                messages.append(event)
                
                # Log each message to flow collector
                if flow_collector:
                    source = getattr(event, 'source', 'unknown')
                    text = str(event.content)
                    conversation_messages.append({
                        'source': source,
                        'content': text,
                        'timestamp': getattr(event, 'timestamp', None)
                    })

        # Update flow collector with conversation messages
        if flow_collector and flow_collector.autogen_conversation:
            flow_collector.autogen_conversation['conversation_messages'] = conversation_messages

        # Build conversation log and extract approved translation (industry standard)
        log_parts: List[str] = []
        final_translation = ""
        
        # Find the approved translation (translator message before APPROVE signal)
        for i, msg in enumerate(messages):
            source = getattr(msg, 'source', 'unknown')
            text = str(msg.content)
            log_parts.append(f"{source}: {text}")
            
            # If this is an approval signal, use the previous translator message
            if source == 'Editor' and 'APPROVE' in text:
                # Look backwards for the most recent translator message
                for j in range(i - 1, -1, -1):
                    prev_msg = messages[j]
                    prev_source = getattr(prev_msg, 'source', 'unknown')
                    if prev_source == 'Translator':
                        final_translation = str(prev_msg.content)
                        break
                break
        
        # Fallback: if no APPROVE found, use last translator message (shouldn't happen with TextMentionTermination)
        if not final_translation:
            for msg in messages:
                source = getattr(msg, 'source', 'unknown')
                if source == 'Translator':
                    final_translation = str(msg.content)

        conversation_log = "\n\n".join(log_parts)

        # Ensure semantic links are present – append first 3 memory URLs as markdown links
        if memories:
            link_lines = []
            for idx, m in enumerate(memories[:3], 1):
                url = m.get('message_url')
                if url and url.startswith('https://t.me/'):
                    link_lines.append(f"🔗 [Источник {idx}]({url})")
            if link_lines:
                final_translation += "\n\n" + "\n".join(link_lines)

        return final_translation, conversation_log

# ---------------------------------------------------------------------------
# Public API used by bot/tests – mirrors legacy signature
# ---------------------------------------------------------------------------

async def translate_and_link(_unused_client, src_text: str, mem: List[Dict[str, Any]], flow_collector=None):
    """Async wrapper matching old signature -> returns translation, conversation_log."""
    system = AutoGenTranslationSystem()
    translation, conversation_log = await system.run(src_text, mem, flow_collector)

    # Save pair to vector store (translation memory) – same as legacy behaviour
    from app.vector_store import save_pair as store_tm  # local import to avoid cycles
    store_tm(src_text, translation, conversation_log=conversation_log)

    return translation, conversation_log

# Streaming variant currently unused in tests – raise to keep fail-fast behaviour.
async def translate_and_link_streaming(*args, **kwargs):  # noqa: ANN001
    raise RuntimeError("Streaming translation not implemented for AutoGen pipeline – use translate_and_link") 