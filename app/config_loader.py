"""
Simple configuration loader for telegram_zoomer bot.
Reads configuration from Supabase REST API.
FAILS LOUDLY when configuration is missing - no defensive coding!
"""

import os
import httpx
from typing import Any, Dict, Optional
import json


class ConfigurationError(Exception):
    """Raised when configuration is missing or invalid"""
    pass


class ConfigLoader:
    """
    Primitive configuration loader using Supabase REST API.
    NO defensive coding - fails loudly when config missing!
    """
    
    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._environment = os.getenv('ENVIRONMENT', 'dev')
        
        # Supabase connection details
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_KEY')
        
        assert self.supabase_url, "SUPABASE_URL environment variable is required"
        assert self.supabase_key, "SUPABASE_KEY environment variable is required"
        
        self.headers = {
            'apikey': self.supabase_key,
            'Authorization': f'Bearer {self.supabase_key}',
            'Content-Type': 'application/json'
        }
    
    def _rest_get(self, table: str, filters: Dict[str, str] = None) -> Dict[str, Any]:
        """Make a REST API call to Supabase."""
        url = f"{self.supabase_url}/rest/v1/{table}"
        
        params = {}
        if filters:
            for key, value in filters.items():
                params[f"{key}"] = f"eq.{value}"
        
        response = httpx.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        
        data = response.json()
        if not data:
            raise ConfigurationError(f"No data found in {table} with filters {filters}")
        
        return data[0] if isinstance(data, list) else data
    
    def get_setting(self, key: str) -> Any:
        """Get a configuration setting by key. FAILS if missing."""
        cache_key = f"setting_{key}"
        
        if cache_key not in self._cache:
            try:
                setting = self._rest_get("bot_config_configsetting", {"key": key})
                value = setting['value']
                
                # Type conversion based on value_type
                value_type = setting.get('value_type', 'str')
                if value_type == 'int':
                    value = int(value)
                elif value_type == 'float':
                    value = float(value)
                elif value_type == 'bool':
                    value = value.lower() in ('true', '1', 'yes', 'on')
                elif value_type == 'json':
                    value = json.loads(value)
                
                self._cache[cache_key] = value
            except Exception as e:
                raise ConfigurationError(f"Configuration setting '{key}' not found in database: {e}")
        
        return self._cache[cache_key]
    
    def get_prompt(self, name: str) -> str:
        """Get a translation prompt by name. FAILS if missing."""
        cache_key = f"prompt_{name}"
        
        if cache_key not in self._cache:
            try:
                prompt = self._rest_get("bot_config_translationprompt", {"name": name, "is_active": "true"})
                self._cache[cache_key] = prompt['content']
            except Exception as e:
                raise ConfigurationError(f"Translation prompt '{name}' not found in database: {e}")
        
        return self._cache[cache_key]
    
    def get_ai_model_config(self) -> Dict[str, Any]:
        """Get the default AI model configuration. FAILS if missing."""
        cache_key = "ai_model_default"
        
        if cache_key not in self._cache:
            try:
                model = self._rest_get("bot_config_aimodelconfig", {"is_default": "true"})
                self._cache[cache_key] = {
                    'model_id': model['model_id'],
                    'max_tokens': model['max_tokens'],
                    'temperature': model['temperature'],
                    'thinking_budget_tokens': model['thinking_budget_tokens'],
                    'timeout_seconds': model['timeout_seconds']
                }
            except Exception as e:
                raise ConfigurationError(f"No default AI model configuration found in database: {e}")
        
        return self._cache[cache_key]
    
    def get_processing_limits(self) -> Dict[str, Any]:
        """Get processing limits for current environment. FAILS if missing."""
        cache_key = f"processing_limits_{self._environment}"
        
        if cache_key not in self._cache:
            try:
                limits = self._rest_get("bot_config_processinglimits", {"environment": self._environment})
                self._cache[cache_key] = {
                    'batch_timeout_seconds': limits['batch_timeout_seconds'],
                    'batch_message_limit': limits['batch_message_limit'],
                    'fetch_timeout_seconds': limits['fetch_timeout_seconds'],
                    'processing_timeout_seconds': limits['processing_timeout_seconds'],
                    'rate_limit_sleep_seconds': limits['rate_limit_sleep_seconds'],
                    'timeout_buffer_seconds': limits['timeout_buffer_seconds']
                }
            except Exception as e:
                raise ConfigurationError(f"Processing limits for environment '{self._environment}' not found in database: {e}")
        
        return self._cache[cache_key]
    
    def get_translation_memory_config(self) -> Dict[str, Any]:
        """Get translation memory configuration. FAILS if missing."""
        cache_key = "translation_memory_config"
        
        if cache_key not in self._cache:
            try:
                config = self._rest_get("bot_config_translationmemoryconfig", {"is_active": "true"})
                self._cache[cache_key] = {
                    'default_recall_k': config['default_recall_k'],
                    'overfetch_multiplier': config['overfetch_multiplier'],
                    'recency_weight': config['recency_weight'],
                    'embedding_model': config['embedding_model'],
                    'embedding_timeout_seconds': config['embedding_timeout_seconds']
                }
            except Exception as e:
                raise ConfigurationError(f"Active translation memory configuration not found in database: {e}")
        
        return self._cache[cache_key]
    
    def get_article_extraction_config(self, domain: str) -> Dict[str, Any]:
        """Get article extraction config for domain. FAILS if missing."""
        cache_key = f"article_extraction_{domain}"
        
        if cache_key not in self._cache:
            try:
                config = self._rest_get("bot_config_articleextractionconfig", {"domain": domain, "is_active": "true"})
                self._cache[cache_key] = {
                    'language_code': config['language_code'],
                    'min_article_length': config['min_article_length'],
                    'timeout_seconds': config['timeout_seconds']
                }
            except Exception as e:
                raise ConfigurationError(f"Article extraction config for domain '{domain}' not found in database: {e}")
        
        return self._cache[cache_key]
    
    def get_message_template(self, name: str) -> str:
        """Get a message template by name. FAILS if missing."""
        cache_key = f"template_{name}"
        
        if cache_key not in self._cache:
            try:
                template = self._rest_get("bot_config_messagetemplate", {"name": name, "is_active": "true"})
                self._cache[cache_key] = template['template']
            except Exception as e:
                raise ConfigurationError(f"Message template '{name}' not found in database: {e}")
        
        return self._cache[cache_key]
    
    def get_environment_config(self) -> Dict[str, Any]:
        """Get environment configuration. FAILS if missing."""
        cache_key = f"environment_config_{self._environment}"
        
        if cache_key not in self._cache:
            try:
                config = self._rest_get("bot_config_environmentconfig", {"environment": self._environment, "is_active": "true"})
                self._cache[cache_key] = {
                    'session_name_pattern': config['session_name_pattern'],
                    'log_level': config['log_level'],
                    'log_format': config['log_format']
                }
            except Exception as e:
                raise ConfigurationError(f"Environment configuration for '{self._environment}' not found in database: {e}")
        
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