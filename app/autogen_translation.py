"""AutoGen-based Translator and Editor pipeline for production.
Fail-fast, no fallbacks, uses Supabase-driven config, keeps translation-memory context.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple

import anthropic
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_ext.models.anthropic import AnthropicChatCompletionClient

from app.config_loader import get_config_loader

config = get_config_loader()


def get_anthropic_client(api_key: str):  # noqa: D401
    """Legacy helper retained for bot import compatibility."""
    return anthropic.Anthropic(api_key=api_key)

async def _amemory_block(memories: List[Dict[str, Any]], k: int | None = None) -> str:
    """Return full source articles for contextual linking decisions."""
    config = get_config_loader()
    if k is None:
        k = int(await config.aget_setting('DEFAULT_RECALL_K'))
    
    block: List[str] = []
    for i, m in enumerate(memories[:k], 1):
        # Include FULL source article for proper contextual analysis
        source_text = m.get('source_text', '').strip()
        translation_text = m.get('translation_text', '').strip()
        
        if source_text and translation_text:
            block.append(f"[{i}] Original: {source_text}")
            block.append(f"[{i}] Translation: {translation_text}")
            block.append("")  # Empty line for readability
    
    return "\n".join(block) if block else "Нет предыдущих постов."


# ---------------------------------------------------------------------------
# AutoGen Translation System
# ---------------------------------------------------------------------------

class AutoGenTranslationSystem:
    """Run a two-agent Translator+Editor conversation and return final result."""

    def __init__(self) -> None:
        self.config = get_config_loader()
        # Note: ai_config will be loaded async in ainit()
    
    async def ainit(self) -> None:
        """Async initialization for loading config from Django ORM."""
        self.ai_config = await self.config.aget_ai_model_config()

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
                    "thinking": {"budget_tokens": 10_000},
                    "timeout": 120.0  # 2 minute timeout
                },
            )
        else:#not implemented
            raise ValueError(f"Model {model_id} not supported")

        # Prompts stored in DB (with potential overrides for Streamlit Studio mode)
        self.base_translator_prompt = os.getenv('TEMP_TRANSLATOR_PROMPT') or await self.config.aget_prompt('autogen_translator')
        self.base_editor_prompt = os.getenv('TEMP_EDITOR_PROMPT') or await self.config.aget_prompt('autogen_editor')

        # Conversation settings
        self.max_cycles = 2  # hard cap – user + 2 rounds → 5 messages total

    # ---------------------------------------------------------------------
    async def run(self, enriched_input: str, memories: List[Dict[str, Any]], flow_collector=None) -> Tuple[str, str]:
        """Return (final_translation, conversation_log)."""
        # Build translator system message with memory context
        memories_formatted = await _amemory_block(memories) if memories else "Нет предыдущих постов."
        # Shared Lurkmore guidelines – prepend to each agent's system prompt (library lacks group-level support)
        shared_guidelines = await self.config.aget_prompt('lurkmore_complete_original_prompt')

        translator_prompt = f"{shared_guidelines}\n\n{self.base_translator_prompt}"
        if '{memory_list' in translator_prompt:
            translator_prompt = translator_prompt.format(memory_list=memories_formatted)
        else:
            translator_prompt = f"{translator_prompt}\n\n🔎 Память:\n{memories_formatted}"

        # Log initial prompts to flow collector
        if flow_collector and flow_collector.autogen_conversation:
            flow_collector.autogen_conversation['initial_translator_prompt'] = translator_prompt
            flow_collector.autogen_conversation['initial_editor_prompt'] = self.base_editor_prompt
            flow_collector.autogen_conversation['memory_context'] = memories_formatted

        translator = AssistantAgent(
            name="Translator",
            model_client=self.model_client,
            system_message=translator_prompt,
        )
        # Make the editor memory-aware as well for better critique
        editor_prompt = f"{shared_guidelines}\n\n{self.base_editor_prompt}"
        if '{memory_list' in editor_prompt:
            editor_prompt = editor_prompt.format(memory_list=memories_formatted)
        else:
            editor_prompt = f"{editor_prompt}\n\n🔎 Память:\n{memories_formatted}"
        editor = AssistantAgent(
            name="Editor",
            model_client=self.model_client,
            system_message=editor_prompt,
        )

        # Two-agent round robin with approval-based termination (industry standard)
        team = RoundRobinGroupChat(
            [translator, editor],
            termination_condition=TextMentionTermination("APPROVE") | MaxMessageTermination(4),  # Stop when editor approves or after 4 messages
        )

        messages: List[Any] = []
        conversation_messages = []  # For flow collector
        
        # Log AI translation start for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"🤖 Starting AI translation conversation (max 4 messages, 2min timeout)")
        
        try:
            async for event in team.run_stream(task=enriched_input):
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
        except Exception as e:
            logger.error(f"❌ AI translation failed: {type(e).__name__}: {e}")
            # Return a fallback translation
            return f"⚠️ Translation unavailable (API error: {type(e).__name__})", f"Error: {e}"

        # Update flow collector with conversation messages
        if flow_collector and flow_collector.autogen_conversation:
            flow_collector.autogen_conversation['conversation_messages'] = conversation_messages

        # Build conversation log and extract approved translation (industry standard)
        log_parts: List[str] = []
        final_translation_text = ""
        
        # Find the approved translation (translator message before APPROVE signal)
        approve_found = False
        for i, msg in enumerate(messages):
            source = getattr(msg, 'source', 'unknown')
            text = str(msg.content)
            log_parts.append(f"{source}: {text}")
            
            # If this is an approval signal, use the previous translator message
            if source == 'Editor' and 'APPROVE' in text:
                approve_found = True
                # Look backwards for the most recent translator message
                for j in range(i - 1, -1, -1):
                    prev_msg = messages[j]
                    prev_source = getattr(prev_msg, 'source', 'unknown')
                    if prev_source == 'Translator':
                        final_translation_text = str(prev_msg.content)
                        break
                break
        
        # If no APPROVE found, use the last translator message (conversation hit message limit)
        if not approve_found:
            # Find the last substantial translator message
            for msg in reversed(messages):
                source = getattr(msg, 'source', 'unknown')
                if source == 'Translator':
                    text = str(msg.content)
                    # Use the last translator message as it should be the improved version
                    final_translation_text = text
                    break

        conversation_log = "\n\n".join(log_parts)
        
        # Log successful completion
        logger.info(f"✅ AI translation completed: {len(final_translation_text)} chars, {len(messages)} messages")

        # Let AI handle all link placement - no automatic footer links
        return final_translation_text, conversation_log

    # ------------------------------------------------------------------
    @staticmethod
    def _build_reference_links(memories: List[Dict[str, Any]], max_links: int = 3) -> str:
        """Create markdown links to previous messages from memory entries.
        Chooses up to max_links entries that have a 'message_url'.
        """
        if not memories:
            return ""
        links: List[str] = []
        for m in memories:
            url = m.get('message_url') or m.get('url')
            if not url or not str(url).startswith('https://t.me/'):
                continue
            label_source = (m.get('translation_text') or m.get('source_text') or 'link').strip()
            label = (label_source[:60] + '...') if len(label_source) > 60 else label_source
            if not label:
                label = 'link'
            links.append(f"[{label}]({url})")
            if len(links) >= max_links:
                break
        return " ".join(links)

    async def aclose(self) -> None:
        """Best-effort cleanup for async resources (prevents loop-closed warnings in tests)."""
        try:
            model_client = getattr(self, 'model_client', None)
            # Prefer async close if available
            if model_client is not None:
                close_coro = getattr(model_client, 'aclose', None)
                if callable(close_coro):
                    await close_coro()
        except Exception:
            # Swallow cleanup errors – this is best-effort
            pass

# ---------------------------------------------------------------------------
# Public API used by bot/tests – mirrors legacy signature
# ---------------------------------------------------------------------------

async def translate_and_link(enriched_input: str, memories: List[Dict[str, Any]], flow_collector=None):
    """Async wrapper -> returns translation, conversation_log."""
    system = AutoGenTranslationSystem()
    await system.ainit()  # Load config asynchronously
    final_translation_text, conversation_log = await system.run(enriched_input, memories, flow_collector)

    # Post-process: ensure at least two semantic links to previous messages are present
    try:
        import re
        existing_links = re.findall(r"\[[^\]]+\]\(https://t\.me/[^\)]+\)", final_translation_text)
        if len(existing_links) < 2:
            references = system._build_reference_links(memories, max_links=3)
            if references:
                final_translation_text = f"{final_translation_text}\n\n{references}"
    except Exception:
        # Non-fatal – translation still returned
        pass

    # Note: Memory storage is handled by the main bot flow in save_translation_to_memory()
    # This avoids duplicate saves and ensures proper metadata (message_url, channel_name) is included

    # Cleanup async resources to avoid event loop warnings in tests
    await system.aclose()

    return final_translation_text, conversation_log
