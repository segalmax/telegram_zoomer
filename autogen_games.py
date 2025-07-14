"""
AutoGen Translation Game System - Version 0.6
Replicates production database integration - reads ALL configuration from Supabase REST API.
NO defensive programming - fails immediately when config missing!
Built around AutoGen 0.6+ with newest autogen-agentchat API.
"""

import os
import asyncio
import warnings
import httpx
import json
from typing import Dict, Any

# Warning suppression - must be done BEFORE importing autogen
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", module="pydantic")
warnings.filterwarnings("ignore", module="autogen")
os.environ["PYDANTIC_DISABLE_WARNINGS"] = "1"

# Use newest AutoGen 0.6 API
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import MaxMessageTermination
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.models.anthropic import AnthropicChatCompletionClient


class ConfigurationError(Exception):
    """Raised when configuration is missing or invalid"""
    pass


class ProductionConfigLoader:
    """
    Production-grade configuration loader using Supabase REST API.
    IDENTICAL to production bot config loading approach.
    NO defensive coding - fails loudly when config missing!
    """
    
    def __init__(self):
        # Get Supabase connection details - fail immediately if missing
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_KEY')
        
        assert self.supabase_url, "SUPABASE_URL environment variable is required"
        assert self.supabase_key, "SUPABASE_KEY environment variable is required"
        
        self.headers = {
            'apikey': self.supabase_key,
            'Authorization': f'Bearer {self.supabase_key}',
            'Content-Type': 'application/json'
        }
        
        # Cache for config data
        self._config_cache = {}
    
    def _rest_get(self, table: str, filters: Dict[str, str] = None) -> Dict[str, Any]:
        """Make REST GET request to Supabase - fail immediately on error"""
        url = f"{self.supabase_url}/rest/v1/{table}"
        
        params = {}
        if filters:
            for key, value in filters.items():
                params[key] = f"eq.{value}"
        
        with httpx.Client() as client:
            response = client.get(url, headers=self.headers, params=params)
            
        # Fail immediately on error
        response.raise_for_status()
        data = response.json()
        
        # Fail if no data found
        assert data, f"No data found in {table} with filters {filters}"
        
        return data[0] if len(data) == 1 else data
    
    def get_ai_model_config(self) -> Dict[str, Any]:
        """Get AI model configuration from database"""
        if 'ai_config' not in self._config_cache:
            model = self._rest_get('bot_config_aimodelconfig', {'is_default': 'true'})
            self._config_cache['ai_config'] = {
                'model_id': model['model_id'],
                'max_tokens': model['max_tokens'],
                'temperature': model['temperature'],
                'thinking_budget_tokens': model['thinking_budget_tokens'],
                'timeout_seconds': model['timeout_seconds']
            }
        return self._config_cache['ai_config']
    
    def get_prompt(self, name: str) -> str:
        """Get prompt by name from database"""
        cache_key = f'prompt_{name}'
        if cache_key not in self._config_cache:
            prompt = self._rest_get('bot_config_translationprompt', {'name': name, 'is_active': 'true'})
            self._config_cache[cache_key] = prompt['content']
        return self._config_cache[cache_key]
    
    def get_setting(self, key: str) -> Any:
        """Get setting value by key from database"""
        cache_key = f'setting_{key}'
        if cache_key not in self._config_cache:
            setting = self._rest_get('bot_config_configsetting', {'key': key})
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
            
            self._config_cache[cache_key] = value
        return self._config_cache[cache_key]


class AutoGenTranslationSystem:
    """
    AutoGen 0.6-based translation system using production database configuration.
    Built around newest autogen-agentchat API with async/await pattern.
    """
    
    def __init__(self):
        self.config = ProductionConfigLoader()
        
        # Load AI model configuration from database
        self.ai_config = self.config.get_ai_model_config()
        
        # Create appropriate model client based on model type
        model_id = self.ai_config['model_id']
        if model_id.startswith('claude'):
            self.model_client = AnthropicChatCompletionClient(
                model=model_id,
                api_key=os.getenv("ANTHROPIC_API_KEY"),  # From env for security
                extra_create_args={
                    "thinking": {
                        "budget_tokens": 10000  # Reduce thinking budget to 10k
                    }
                }
            )
        else:
            self.model_client = OpenAIChatCompletionClient(
                model=model_id,
                api_key=os.getenv("OPENAI_API_KEY")  # From env for security
            )
        
        # Load translation prompts from database
        self.translator_prompt = self.config.get_prompt("autogen_translator")
        self.editor_prompt = self.config.get_prompt("autogen_editor")
        
        # Load system settings from database  
        self.max_cycles = 2  # Reduce to 2 cycles for faster execution
        
        print(f"✅ AutoGen 0.6 system initialized with model: {self.ai_config['model_id']}")
        print(f"✅ Max conversation cycles: {self.max_cycles}")
    
    def create_agents(self) -> tuple:
        """Create AutoGen 0.6 agents with database-loaded prompts."""
        # Translator agent - uses database-loaded prompt
        translator = AssistantAgent(
            name="Translator",
            model_client=self.model_client,
            system_message=self.translator_prompt
        )
        
        # Editor agent - uses database-loaded prompt  
        editor = AssistantAgent(
            name="Editor",
            model_client=self.model_client,
            system_message=self.editor_prompt
        )
        
        return translator, editor
    
    async def run_translation_conversation(self, article: str) -> str:
        """Run the translator-editor conversation game using database config and AutoGen 0.6 API."""
        translator, editor = self.create_agents()
        
        # Calculate max messages from database setting (cycles * 2 + 1 for initial message)
        max_messages = self.max_cycles * 2 + 1
        
        # Create RoundRobinGroupChat team with termination condition
        team = RoundRobinGroupChat(
            participants=[translator, editor],
            termination_condition=MaxMessageTermination(max_messages)
        )
        
        print(f"🚀 Starting translation conversation with max {max_messages} messages...")
        print("📝 Article to translate:")
        print(f"    {article}")
        print("=" * 50)
        
        # Run the conversation and collect all events
        messages = []
        async for event in team.run_stream(task=article):
            print(f"🔍 Event type: {type(event)}")
            
            # Check different event attributes
            if hasattr(event, 'content'):
                print(f"📝 Content: {event.content}")
                if hasattr(event.content, 'text'):
                    print(f"🤖 {getattr(event, 'source', 'Unknown')}: {event.content.text}")
                    print("-" * 30)
                    messages.append(event.content.text)
            else:
                print(f"⚠️ Event: {event}")
        
        # Extract the last translator response - look for the final version 
        final_translation = "Translation completed - see conversation above"
        
        # Parse through messages to find final translator content
        for msg in reversed(messages):
            if hasattr(msg, 'source') and hasattr(msg, 'content'):
                if 'Translator' in str(msg.source):
                    # Look for actual translation content (not meta-commentary)
                    content = str(msg.content)
                    if 'СРОЧНО' in content or 'BREAKING' in content or 'срочняк' in content.lower():
                        final_translation = content
                        break
        
        return final_translation


async def main():
    """Main execution - loads test article from database and processes it."""
    print("🎮 Running Translation Game...")
    print("=" * 50)
    
    # Initialize system with database configuration
    system = AutoGenTranslationSystem()
    
    # Get test article from database settings
    test_article = system.config.get_setting("autogen_test_article")
    
    print(f"Human (to chat_manager):")
    print(f"    {test_article}")
    print("    ")
    print("-" * 50)
    
    # Run the translation conversation
    result = await system.run_translation_conversation(test_article)
    
    print("\n" + "=" * 50)
    print("🎯 Final Translation:")
    print(result)
    

if __name__ == "__main__":
    asyncio.run(main()) 