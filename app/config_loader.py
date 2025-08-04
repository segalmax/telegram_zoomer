"""
Minimal configuration loader for telegram_zoomer.
Uses Django ORM for consistent database access and automatic audit logging.
~40 LOC by design – no caching, no type-conversions, no defensive fallbacks.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

# Bootstrap Django ORM
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config_admin.settings")
django.setup()

from django.db import transaction
from asgiref.sync import sync_to_async
from bot_config import models as m


class ConfigurationError(Exception):
    """Raised when configuration is missing or invalid."""


class ConfigLoader:
    """Primitive one-shot configuration loader using Django ORM."""

    def __init__(self) -> None:
        from .database_config import get_database_config
        
        config = get_database_config()
        print(config["description"])
        
        # Expose for legacy code – remove when callers are updated
        self.supabase_url: str = config["url"] 
        self.supabase_key: str = config["api_key"]

        self._env: str = os.getenv("ENVIRONMENT", "dev")

    # ------------------------------------------------------------------
    # Public, minimal API used elsewhere in the code-base (Django ORM)
    # ------------------------------------------------------------------
    def get_setting(self, key: str) -> Any:
        try:
            obj = m.ConfigSetting.objects.get(key=key)
            return obj.value
        except m.ConfigSetting.DoesNotExist:
            raise ConfigurationError(f"Setting '{key}' not found")

    def get_prompt(self, name: str) -> str:
        try:
            obj = m.TranslationPrompt.objects.get(name=name, is_active=True)
            return obj.content
        except m.TranslationPrompt.DoesNotExist:
            raise ConfigurationError(f"Prompt '{name}' not found")

    def get_ai_model_config(self) -> Dict[str, Any]:
        obj = m.AIModelConfig.objects.filter(is_default=True).first()
        if not obj:
            raise ConfigurationError("Default AI model config not found")
        return {
            'id': obj.id,
            'name': obj.name,
            'provider': obj.provider,
            'model_id': obj.model_id,
            'max_tokens': obj.max_tokens,
            'temperature': float(obj.temperature),
            'thinking_budget_tokens': obj.thinking_budget_tokens,
            'timeout_seconds': obj.timeout_seconds,
            'is_default': obj.is_default,
            'created_at': obj.created_at.isoformat(),
            'updated_at': obj.updated_at.isoformat(),
        }

    # Async versions for use in async contexts (like Telegram bot)
    async def aget_ai_model_config(self) -> Dict[str, Any]:
        return await sync_to_async(self.get_ai_model_config)()
    
    async def aget_prompt(self, name: str) -> str:
        return await sync_to_async(self.get_prompt)(name)
    
    async def aget_setting(self, key: str) -> Any:
        return await sync_to_async(self.get_setting)(key)

    def get_processing_limits(self) -> Dict[str, Any]:
        obj = m.ProcessingLimits.objects.filter(environment=self._env).first()
        if not obj:
            raise ConfigurationError(f"Processing limits for '{self._env}' not found")
        return {
            'environment': obj.environment,
            'batch_timeout_seconds': obj.batch_timeout_seconds,
            'batch_message_limit': obj.batch_message_limit,
            'fetch_timeout_seconds': obj.fetch_timeout_seconds,
            'processing_timeout_seconds': obj.processing_timeout_seconds,
            'rate_limit_sleep_seconds': float(obj.rate_limit_sleep_seconds),
            'timeout_buffer_seconds': obj.timeout_buffer_seconds,
        }

    def get_article_extraction_config(self, domain: str) -> Dict[str, Any]:
        try:
            obj = m.ArticleExtractionConfig.objects.get(domain=domain)
            return {
                'domain': obj.domain,
                'language_code': obj.language_code,
                'min_article_length': obj.min_article_length,
                'timeout_seconds': obj.timeout_seconds,
            }
        except m.ArticleExtractionConfig.DoesNotExist:
            raise ConfigurationError(f"Article extraction config for '{domain}' not found")

    def get_translation_memory_config(self) -> Dict[str, Any]:
        obj = m.TranslationMemoryConfig.objects.filter(is_active=True).first()
        if not obj:
            raise ConfigurationError("Active translation memory config not found")
        return {
            'id': obj.id,
            'name': obj.name,
            'default_recall_k': obj.default_recall_k,
            'overfetch_multiplier': obj.overfetch_multiplier,
            'recency_weight': float(obj.recency_weight),
            'embedding_model': obj.embedding_model,
            'embedding_timeout_seconds': obj.embedding_timeout_seconds,
            'is_active': obj.is_active,
        }

    def get_environment_config(self) -> Dict[str, Any]:
        obj = m.EnvironmentConfig.objects.filter(environment=self._env).first()
        if not obj:
            raise ConfigurationError(f"Environment config for '{self._env}' not found")
        return {
            'environment': obj.environment,
            'session_name_pattern': obj.session_name_pattern,
            'log_level': obj.log_level,
            'log_format': obj.log_format,
        }

    def get_message_template(self, name: str) -> str:
        try:
            obj = m.MessageTemplate.objects.get(name=name)
            return obj.template
        except m.MessageTemplate.DoesNotExist:
            raise ConfigurationError(f"Message template '{name}' not found")


# -------------------------------------------------------------------------
# Global singleton (kept for convenience but easy to drop if undesired)
# -------------------------------------------------------------------------
_config_loader: Optional[ConfigLoader] = None

def get_config_loader() -> ConfigLoader:
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader()
    return _config_loader
