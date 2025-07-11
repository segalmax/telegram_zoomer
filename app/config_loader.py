"""
Simple configuration loader for telegram_zoomer bot.
Reads configuration from Django database models.
FAILS LOUDLY when configuration is missing - no defensive coding!
"""

import os
import sys
import django
from typing import Any, Dict, Optional

# Configure Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config_admin.settings')
django.setup()

from bot_config.models import (
    ConfigSetting, TranslationPrompt, AIModelConfig, 
    ProcessingLimits, TranslationMemoryConfig, ArticleExtractionConfig,
    MessageTemplate, EnvironmentConfig
)


class ConfigurationError(Exception):
    """Raised when configuration is missing or invalid"""
    pass


class ConfigLoader:
    """
    Primitive configuration loader.
    NO defensive coding - fails loudly when config missing!
    """
    
    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._environment = os.getenv('ENVIRONMENT', 'dev')
    
    def get_setting(self, key: str) -> Any:
        """Get a configuration setting by key. FAILS if missing."""
        cache_key = f"setting_{key}"
        
        if cache_key not in self._cache:
            try:
                setting = ConfigSetting.objects.get(key=key)
                self._cache[cache_key] = setting.get_typed_value()
            except ConfigSetting.DoesNotExist:
                raise ConfigurationError(f"Configuration setting '{key}' not found in database!")
        
        return self._cache[cache_key]
    
    def get_prompt(self, name: str) -> str:
        """Get a translation prompt by name. FAILS if missing."""
        cache_key = f"prompt_{name}"
        
        if cache_key not in self._cache:
            try:
                prompt = TranslationPrompt.objects.get(name=name, is_active=True)
                self._cache[cache_key] = prompt.content
            except TranslationPrompt.DoesNotExist:
                raise ConfigurationError(f"Translation prompt '{name}' not found in database!")
        
        return self._cache[cache_key]
    

    
    def get_ai_model_config(self) -> Dict[str, Any]:
        """Get the default AI model configuration. FAILS if missing."""
        cache_key = "ai_model_default"
        
        if cache_key not in self._cache:
            try:
                model = AIModelConfig.objects.get(is_default=True)
                self._cache[cache_key] = {
                    'model_id': model.model_id,
                    'max_tokens': model.max_tokens,
                    'temperature': model.temperature,
                    'thinking_budget_tokens': model.thinking_budget_tokens,
                    'timeout_seconds': model.timeout_seconds
                }
            except AIModelConfig.DoesNotExist:
                raise ConfigurationError("No default AI model configuration found in database!")
        
        return self._cache[cache_key]
    
    def get_processing_limits(self) -> Dict[str, Any]:
        """Get processing limits for current environment. FAILS if missing."""
        cache_key = f"processing_limits_{self._environment}"
        
        if cache_key not in self._cache:
            try:
                limits = ProcessingLimits.objects.get(environment=self._environment)
                self._cache[cache_key] = {
                    'batch_timeout_seconds': limits.batch_timeout_seconds,
                    'batch_message_limit': limits.batch_message_limit,
                    'fetch_timeout_seconds': limits.fetch_timeout_seconds,
                    'processing_timeout_seconds': limits.processing_timeout_seconds,
                    'rate_limit_sleep_seconds': limits.rate_limit_sleep_seconds,
                    'timeout_buffer_seconds': limits.timeout_buffer_seconds
                }
            except ProcessingLimits.DoesNotExist:
                raise ConfigurationError(f"Processing limits for environment '{self._environment}' not found in database!")
        
        return self._cache[cache_key]
    
    def get_translation_memory_config(self) -> Dict[str, Any]:
        """Get translation memory configuration. FAILS if missing."""
        cache_key = "translation_memory_config"
        
        if cache_key not in self._cache:
            try:
                config = TranslationMemoryConfig.objects.get(is_active=True)
                self._cache[cache_key] = {
                    'default_recall_k': config.default_recall_k,
                    'overfetch_multiplier': config.overfetch_multiplier,
                    'recency_weight': config.recency_weight,
                    'embedding_model': config.embedding_model,
                    'embedding_timeout_seconds': config.embedding_timeout_seconds
                }
            except TranslationMemoryConfig.objects.DoesNotExist:
                raise ConfigurationError("Active translation memory configuration not found in database!")
        
        return self._cache[cache_key]
    
    def get_article_extraction_config(self, domain: str) -> Dict[str, Any]:
        """Get article extraction config for domain. FAILS if missing."""
        cache_key = f"article_extraction_{domain}"
        
        if cache_key not in self._cache:
            try:
                config = ArticleExtractionConfig.objects.get(domain=domain, is_active=True)
                self._cache[cache_key] = {
                    'language_code': config.language_code,
                    'min_article_length': config.min_article_length,
                    'timeout_seconds': config.timeout_seconds
                }
            except ArticleExtractionConfig.DoesNotExist:
                raise ConfigurationError(f"Article extraction config for domain '{domain}' not found in database!")
        
        return self._cache[cache_key]
    
    def get_message_template(self, name: str) -> str:
        """Get a message template by name. FAILS if missing."""
        cache_key = f"template_{name}"
        
        if cache_key not in self._cache:
            try:
                template = MessageTemplate.objects.get(name=name, is_active=True)
                self._cache[cache_key] = template.template
            except MessageTemplate.DoesNotExist:
                raise ConfigurationError(f"Message template '{name}' not found in database!")
        
        return self._cache[cache_key]
    
    def get_environment_config(self) -> Dict[str, Any]:
        """Get environment configuration. FAILS if missing."""
        cache_key = f"environment_config_{self._environment}"
        
        if cache_key not in self._cache:
            try:
                config = EnvironmentConfig.objects.get(environment=self._environment, is_active=True)
                self._cache[cache_key] = {
                    'session_name_pattern': config.session_name_pattern,
                    'log_level': config.log_level,
                    'log_format': config.log_format
                }
            except EnvironmentConfig.DoesNotExist:
                raise ConfigurationError(f"Environment configuration for '{self._environment}' not found in database!")
        
        return self._cache[cache_key]
    
    def clear_cache(self):
        """Clear the configuration cache."""
        self._cache.clear()


# Global singleton instance
_config_loader = None

def get_config_loader() -> ConfigLoader:
    """Get the global config loader instance."""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader()
    return _config_loader 