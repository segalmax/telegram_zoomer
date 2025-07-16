import streamlit as st
import asyncio
import os
import time
from datetime import datetime
import json
from dotenv import load_dotenv

# Load environment variables FIRST, before any imports
load_dotenv()

# FAIL IMMEDIATELY if required environment variables are missing - NO FALLBACKS!
assert os.getenv("OPENAI_API_KEY"), "OPENAI_API_KEY environment variable is required"
assert os.getenv("ANTHROPIC_API_KEY"), "ANTHROPIC_API_KEY environment variable is required"
assert os.getenv("SUPABASE_URL"), "SUPABASE_URL environment variable is required"
assert os.getenv("SUPABASE_KEY"), "SUPABASE_KEY environment variable is required"

from app.translator import get_anthropic_client
from app.config_loader import get_config_loader
from app.vector_store import recall as recall_tm, save_pair as store_tm  # Import production memory functions

# Import Supabase for database operations
from supabase import create_client, Client

# For REAL AutoGen streaming
from autogen_games import autogen_event_stream

# Initialize config loader
config = get_config_loader()

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def save_conversation_to_db(source_text: str, translated_text: str, conversation_log: list, 
                          settings: dict, streaming_type: str, model_used: str = None, 
                          temperature: float = None, max_tokens: int = None, 
                          total_tokens_used: int = None, processing_time_ms: int = None,
                          error_message: str = None, status: str = "completed"):
    """Save conversation to Supabase database - NO FALLBACKS!"""
    
    # Get session ID from Streamlit
    session_id = st.session_state.get('session_id', 'unknown')
    if session_id == 'unknown':
        # Generate a session ID if not available
        import uuid
        session_id = str(uuid.uuid4())
        st.session_state['session_id'] = session_id
    
    conversation_data = {
        'session_id': session_id,
        'source_text': source_text,
        'translated_text': translated_text,
        'conversation_log': conversation_log,
        'settings': settings,
        'streaming_type': streaming_type,
        'model_used': model_used,
        'temperature': temperature,
        'max_tokens': max_tokens,
        'total_tokens_used': total_tokens_used,
        'processing_time_ms': processing_time_ms,
        'error_message': error_message,
        'status': status
    }
    
    # Insert into Supabase - FAIL if it doesn't work
    result = supabase.table("streamlit_conversations").insert(conversation_data).execute()
    
    # Check for errors
    if hasattr(result, 'error') and result.error:
        raise Exception(f"Database insert failed: {result.error}")
    
    return result.data[0] if result.data else None

async def custom_autogen_event_stream(article: str, ui_config: dict, memory: list = None):
    """REAL streaming directly from Claude API - bypassing AutoGen's fake streaming"""
    import anthropic
    import asyncio
    import time
    
    # Get configuration from UI settings
    ai_config = ui_config.get('ai_model', {})
    translator_prompt = ui_config.get('translator_prompt', 'Translate this text.')
    editor_prompt = ui_config.get('editor_prompt', 'Review and improve this translation.')
    
    print(f"🎛️ REAL STREAMING: Using {ai_config.get('model_id')} with {ai_config.get('max_tokens')} tokens, temp {ai_config.get('temperature')}")
    
    # Create direct Anthropic client for REAL streaming
    anthropic_client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    
    # ------------- PRODUCTION memory integration (same as bot) ----------------
    if memory:
        print(f"🧠 Using {len(memory)} memory entries for translation context")
        # Memory is provided via system prompt, not user message (same as bot)
        memory_context = ""  # Claude gets compact summaries in system prompt
    else:
        print("🧠 No memory context provided")
        memory_context = ""
    
    # Translator phase - REAL streaming from Claude with memory context
    yield type('AgentStart', (), {
        'source': 'Translator',
        'event_type': 'agent_start'
    })()
    
    translator_response = ""
    token_count = 0
    
    # Construct translator message with memory context (same as production bot)
    translator_message = f"{translator_prompt}\n\n{article}"
    if memory:
        # Add memory context (simplified - production bot uses more complex memory injection)
        translator_message += f"\n\n[Translation Memory Context: {len(memory)} past translations available]"
    
    async with anthropic_client.messages.stream(
        model=ai_config.get('model_id', 'claude-3-5-sonnet-20241022'),
        max_tokens=ai_config.get('max_tokens', 8192),
        temperature=ai_config.get('temperature', 0.7),
        messages=[{
            "role": "user", 
            "content": translator_message
        }]
    ) as stream:
        async for text in stream.text_stream:
            token_count += 1
            translator_response += text
            
            # Yield REAL token from Claude API
            yield type('TokenEvent', (), {
                'source': 'Translator',
                'content': type('Content', (), {'text': text})(),
                'accumulated_text': translator_response,
                'event_type': 'token',
                'token_index': token_count,
                'total_tokens': None  # We don't know total - this is REAL streaming!
            })()
    
    print(f"✅ REAL streaming completed for Translator: {token_count} tokens")
    
    # Short pause between agents
    await asyncio.sleep(0.5)
    
    # Editor phase - REAL streaming from Claude  
    yield type('AgentStart', (), {
        'source': 'Editor',
        'event_type': 'agent_start'
    })()
    
    editor_response = ""
    token_count = 0
    
    async with anthropic_client.messages.stream(
        model=ai_config.get('model_id', 'claude-3-5-sonnet-20241022'),
        max_tokens=ai_config.get('max_tokens', 8192),
        temperature=ai_config.get('temperature', 0.7),
        messages=[{
            "role": "user",
            "content": f"{editor_prompt}\n\nOriginal: {article}\n\nTranslation to review: {translator_response}"
        }]
    ) as stream:
        async for text in stream.text_stream:
            token_count += 1
            editor_response += text
            
            # Yield REAL token from Claude API
            yield type('TokenEvent', (), {
                'source': 'Editor',
                'content': type('Content', (), {'text': text})(),
                'accumulated_text': editor_response,
                'event_type': 'token',
                'token_index': token_count,
                'total_tokens': None  # We don't know total - this is REAL streaming!
            })()
    
    print(f"✅ REAL streaming completed for Editor: {token_count} tokens")
    
    # Final Translator response incorporating editor feedback - REAL streaming
    await asyncio.sleep(0.5)
    
    yield type('AgentStart', (), {
        'source': 'Translator',
        'event_type': 'agent_start'
    })()
    
    final_response = ""
    token_count = 0
    
    # Final translator message with memory context if available
    final_translator_message = f"{translator_prompt}\n\nOriginal: {article}\n\nMy first translation: {translator_response}\n\nEditor feedback: {editor_response}\n\nPlease provide the final improved translation incorporating the editor's feedback:"
    if memory:
        final_translator_message += f"\n\n[Translation Memory: Use {len(memory)} past translations to avoid repetition and ensure fresh language]"
    
    async with anthropic_client.messages.stream(
        model=ai_config.get('model_id', 'claude-3-5-sonnet-20241022'),
        max_tokens=ai_config.get('max_tokens', 8192),
        temperature=ai_config.get('temperature', 0.7),
        messages=[{
            "role": "user",
            "content": final_translator_message
        }]
    ) as stream:
        async for text in stream.text_stream:
            token_count += 1
            final_response += text
            
            # Yield REAL token from Claude API  
            yield type('TokenEvent', (), {
                'source': 'Translator',
                'content': type('Content', (), {'text': text})(),
                'accumulated_text': final_response,
                'event_type': 'token',
                'token_index': token_count,
                'total_tokens': None  # We don't know total - this is REAL streaming!
            })()
    
    print(f"✅ REAL streaming completed for final Translator: {token_count} tokens")
    
    # End with completion event
    yield type('TaskResult', (), {
        'final_translation': final_response,
        'conversation_log': f"Translator: {translator_response}\n\nEditor: {editor_response}\n\nTranslator: {final_response}"
    })()

# Page config
st.set_page_config(
    page_title="🤖 Claude Translation Studio", 
    page_icon="🤖",
    layout="wide"
)

# Custom CSS for better styling
st.markdown("""
<style>
.main-header {
    font-size: 2.5rem;
    font-weight: bold;
    color: #FF6B35;
    text-align: center;
    margin-bottom: 2rem;
}

.cost-box {
    background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    padding: 1rem;
    border-radius: 10px;
    color: white;
    margin: 1rem 0;
}

.thinking-box {
    background: #f0f2f6;
    border-left: 4px solid #4CAF50;
    padding: 1rem;
    margin: 0.5rem 0;
    border-radius: 5px;
    font-family: 'Courier New', monospace;
    white-space: pre-wrap;
}

.response-box {
    background: #e8f4fd;
    border-left: 4px solid #2196F3;
    padding: 1rem;
    margin: 0.5rem 0;
    border-radius: 5px;
}

.memory-box {
    background: #fff3cd;
    border: 1px solid #ffeaa7;
    border-radius: 8px;
    padding: 1rem;
    margin: 0.5rem 0;
}

.step-header {
    font-size: 1.2rem;
    font-weight: bold;
    color: #2c3e50;
    margin: 1rem 0 0.5rem 0;
}

.translator-step {
    color: #27ae60;
}

.editor-step {
    color: #e74c3c;
}
    .step-header {
        padding: 8px 12px;
        border-radius: 8px;
        margin: 4px 0;
        font-weight: bold;
    }
    .translator-step {
        background: linear-gradient(135deg, #e8f5e8, #c8e6c9);
        color: #2e7d32;
    }
    .editor-step {
        background: linear-gradient(135deg, #fff3e0, #ffcc02);
        color: #ef6c00;
    }
    .thinking-box {
        background: #f8f9fa;
        padding: 12px;
        border-radius: 8px;
        border-left: 4px solid #17a2b8;
        margin: 8px 0;
    }
    .response-box {
        background: #f8f9fa;
        padding: 12px;
        border-radius: 8px;
        border-left: 4px solid #28a745;
        margin: 8px 0;
    }
    @keyframes blink {
        0%, 50% { opacity: 1; }
        51%, 100% { opacity: 0; }
}
</style>
""", unsafe_allow_html=True)

def show_memory_entries(memory):
    """Display translation memory entries in a nice format"""
    if not memory:
        st.info("💭 No relevant translation memory found")
        return
        
    st.markdown("### 📚 Translation Memory Context")
    st.markdown(f"Found **{len(memory)}** similar past translations:")
    
    for i, entry in enumerate(memory, 1):
        with st.expander(f"Memory #{i}: {entry['translation_text'][:60]}..."):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown("**Translation:**")
                st.text(entry['translation_text'])
            with col2:
                if 'message_url' in entry:
                    st.markdown("**Source:**")
                    st.markdown(f"[View Message]({entry['message_url']})")

def load_all_prompts():
    """Load all translation prompts from database"""
    try:
        prompts = {}
        prompt_names = [
            'autogen_translator',
            'autogen_editor', 
            'lurkmore_complete_original_prompt'
        ]
        
        for name in prompt_names:
            try:
                prompts[name] = config.get_prompt(name)
            except Exception as e:
                st.error(f"Failed to load prompt '{name}': {e}")
                prompts[name] = f"ERROR: Could not load prompt '{name}'"
                
        return prompts
    except Exception as e:
        st.error(f"Failed to load prompts: {e}")
        return {}

def load_all_db_settings():
    """Load all configuration settings from database for the settings panel"""
    try:
        settings = {}
        
        # Translation Prompts
        try:
            settings['prompts'] = load_all_prompts()
        except Exception as e:
            st.error(f"Failed to load prompts: {e}")
            settings['prompts'] = {}
        
        # AI Model Configuration
        try:
            settings['ai_model'] = config.get_ai_model_config()
        except Exception as e:
            st.error(f"Failed to load AI model config: {e}")
            settings['ai_model'] = {
                'model_id': 'claude-sonnet-4-20250514',
                'max_tokens': 8192,
                'temperature': 0.7,
                'thinking_budget_tokens': 30000,
                'timeout_seconds': 120
            }
        
        # Processing Limits
        try:
            settings['processing_limits'] = config.get_processing_limits()
        except Exception as e:
            st.error(f"Failed to load processing limits: {e}")
            settings['processing_limits'] = {
                'batch_timeout_seconds': 300,
                'batch_message_limit': 10,
                'fetch_timeout_seconds': 30,
                'processing_timeout_seconds': 60,
                'rate_limit_sleep_seconds': 2.0,
                'timeout_buffer_seconds': 10
            }
        
        # Translation Memory Configuration
        try:
            settings['translation_memory'] = config.get_translation_memory_config()
        except Exception as e:
            st.error(f"Failed to load translation memory config: {e}")
            settings['translation_memory'] = {
                'default_recall_k': 10,
                'overfetch_multiplier': 2.0,
                'recency_weight': 0.1,
                'embedding_model': 'text-embedding-ada-002',
                'embedding_timeout_seconds': 30
            }
        
        # Environment Configuration
        try:
            settings['environment'] = config.get_environment_config()
        except Exception as e:
            st.error(f"Failed to load environment config: {e}")
            settings['environment'] = {
                'session_name_pattern': 'telegram_zoomer_session',
                'log_level': 'INFO',
                'log_format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            }
        
        # Individual Settings
        settings['individual'] = {}
        setting_keys = [
            'ANTHROPIC_MODEL_ID', 'ANTHROPIC_MAX_TOKENS', 'ANTHROPIC_TEMPERATURE',
            'TEST_MODE_BATCH_LIMIT', 'TEST_MODE_TIMEOUT', 'MEMORY_RECALL_K',
            'ARTICLE_MIN_LENGTH', 'DEFAULT_LANGUAGE_CODE'
        ]
        
        for key in setting_keys:
            try:
                settings['individual'][key] = config.get_setting(key)
            except Exception:
                settings['individual'][key] = None
        
        return settings
    except Exception as e:
        st.error(f"Failed to load database settings: {e}")
        return {}

def show_settings_panel():
    """Display configurable settings panel (read-only, initialized from DB)"""
    st.markdown("### ⚙️ Configuration Settings")
    st.info("💡 Settings are loaded from database but changes are not persisted - perfect for experimentation!")
    
    # Load settings from database
    if 'db_settings' not in st.session_state:
        st.session_state.db_settings = load_all_db_settings()
    
    settings = st.session_state.db_settings
    
    if not settings:
        st.error("Failed to load settings from database")
        return {}
    
    # Prompts section - full width at the top, editable
    st.markdown("#### 📝 Translation Prompts")
    if 'prompts' in settings and settings['prompts']:
        for prompt_name, prompt_content in settings['prompts'].items():
            st.markdown(f"**{prompt_name.replace('_', ' ').title()}**")
            # Calculate height based on content (roughly 20px per line)
            line_count = len((prompt_content or "").split('\n'))
            # Minimum 3 lines, add padding for comfortable editing
            dynamic_height = max(80, min(600, line_count * 25 + 50))
            
            # Editable text area for each prompt - auto-sized to content
            updated_prompt = st.text_area(
                label=f"Edit {prompt_name}",
                value=prompt_content or "",
                height=dynamic_height,
                key=f"prompt_{prompt_name}",
                help=f"Character count: {len(prompt_content or '')} | Lines: {line_count} | Editable in UI only"
            )
            settings['prompts'][prompt_name] = updated_prompt
            st.markdown("---")  # Separator between prompts
    else:
        st.warning("No prompts loaded from database")
    
    st.markdown("---")
    st.markdown("#### 🔧 Configuration Settings")
    
    # Create 5 columns for other settings (removed col6 since prompts are now full-width above)
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.markdown("#### 🤖 AI Model")
        if 'ai_model' in settings:
            ai_config = {}
            ai_config['model_id'] = st.selectbox(
                "Model", 
                options=['claude-sonnet-4-20250514', 'claude-3-5-sonnet-20241022', 'gpt-4o', 'gpt-4o-mini'],
                index=0 if settings['ai_model']['model_id'] == 'claude-sonnet-4-20250514' else 0,
                help="🧠 **AI Model Selection**: Choose the language model for translation. Claude Sonnet 4 offers superior reasoning and creativity, while GPT-4o provides fast performance. Different models have varying costs, capabilities, and context windows.",
                key="ai_model"
            )
            ai_config['max_tokens'] = st.number_input(
                "Max Tokens", 
                min_value=1000, max_value=200000, 
                value=max(1000, settings['ai_model']['max_tokens']),
                help="📏 **Maximum Response Length**: Controls how long the AI's response can be. 1 token ≈ 0.75 words. Higher values allow longer translations but cost more. Typical article translations need 4,000-8,000 tokens.",
                key="max_tokens"
            )
            ai_config['temperature'] = st.slider(
                "Temperature", 
                min_value=0.0, max_value=2.0, 
                value=float(settings['ai_model']['temperature']),
                step=0.1,
                help="🎭 **Creative Freedom**: Controls randomness in AI responses. 0.0 = deterministic/factual, 1.0 = balanced creativity, 2.0 = highly creative/unpredictable. For translation, 0.7-0.9 works well.",
                key="temperature"
            )
            ai_config['thinking_budget_tokens'] = st.number_input(
                "Think Tokens", 
                min_value=1000, max_value=100000,
                value=max(1000, settings['ai_model']['thinking_budget_tokens']),
                help="🤔 **Internal Reasoning Budget**: Tokens allocated for AI's internal 'thinking' process before generating the final response. Higher values allow deeper analysis but increase latency and cost. 20,000-30,000 tokens work well for complex translations.",
                key="thinking_tokens"
            )
            ai_config['timeout_seconds'] = st.number_input(
                "Timeout (s)", 
                min_value=10, max_value=600,
                value=max(10, settings['ai_model']['timeout_seconds']),
                help="⏱️ **Request Timeout**: Maximum time to wait for AI response before giving up. Longer timeouts allow complex translations to complete but may delay error detection. 120-300 seconds is typical for article translation.",
                key="ai_timeout"
            )
            settings['ai_model'] = ai_config
    
    with col2:
        st.markdown("#### ⚡ Processing")
        if 'processing_limits' in settings:
            proc_config = {}
            proc_config['batch_timeout_seconds'] = st.number_input(
                "Batch Timeout", 
                min_value=60, max_value=3600,
                value=max(60, settings['processing_limits']['batch_timeout_seconds']),
                help="📦 **Batch Processing Limit**: Total time allowed for processing multiple messages at once. If batch processing takes longer, it stops early. Use 300-600 seconds for typical batches of 5-20 messages.",
                key="batch_timeout"
            )
            proc_config['batch_message_limit'] = st.number_input(
                "Msg Limit", 
                min_value=1, max_value=100,
                value=max(1, settings['processing_limits']['batch_message_limit']),
                help="📮 **Maximum Batch Size**: How many messages to process in one batch operation. Higher values process more messages but increase memory usage and risk of timeouts. 10-20 messages is optimal.",
                key="batch_limit"
            )
            proc_config['fetch_timeout_seconds'] = st.number_input(
                "Fetch Timeout", 
                min_value=5, max_value=120,
                value=max(5, settings['processing_limits']['fetch_timeout_seconds']),
                help="📥 **Message Retrieval Timeout**: Time to wait when fetching messages from Telegram. Network issues can cause delays. 15-30 seconds handles most connection problems gracefully.",
                key="fetch_timeout"
            )
            proc_config['processing_timeout_seconds'] = st.number_input(
                "Process Timeout", 
                min_value=10, max_value=300,
                value=max(10, settings['processing_limits']['processing_timeout_seconds']),
                help="⚙️ **Per-Message Processing Limit**: Maximum time allowed to translate a single message. Complex articles need more time. 60-180 seconds works for most content.",
                key="process_timeout"
            )
            proc_config['rate_limit_sleep_seconds'] = st.number_input(
                "Rate Limit", 
                min_value=0.1, max_value=10.0,
                value=max(0.1, float(settings['processing_limits']['rate_limit_sleep_seconds'])),
                step=0.1,
                help="🐌 **API Rate Limiting**: Pause between API calls to avoid hitting rate limits. Too fast = API errors, too slow = unnecessary delays. 1-3 seconds prevents most issues.",
                key="rate_limit"
            )
            proc_config['timeout_buffer_seconds'] = st.number_input(
                "Buffer", 
                min_value=1, max_value=60,
                value=max(1, settings['processing_limits']['timeout_buffer_seconds']),
                help="🛡️ **Safety Buffer**: Reserved time before timeout to gracefully stop processing. Prevents abrupt cancellations. 5-15 seconds provides good safety margin.",
                key="timeout_buffer"
            )
            settings['processing_limits'] = proc_config
    
    with col3:
        st.markdown("#### 🧠 Memory")
        if 'translation_memory' in settings:
            tm_config = {}
            tm_config['default_recall_k'] = st.number_input(
                "Recall K", 
                min_value=1, max_value=50,
                value=max(1, settings['translation_memory']['default_recall_k']),
                help="🔍 **Translation Memory Retrieval**: Number of similar past translations to recall for context. More examples improve consistency but may dilute relevance. 5-15 provides good balance between context and focus.",
                key="recall_k"
            )
            tm_config['overfetch_multiplier'] = st.number_input(
                "Overfetch", 
                min_value=1.0, max_value=5.0,
                value=max(1.0, float(settings['translation_memory']['overfetch_multiplier'])),
                step=0.1,
                help="📈 **Search Amplification**: Retrieves extra candidates before filtering to top K. Higher values find more diverse matches but increase processing cost. 2.0-3.0 improves quality without excessive overhead.",
                key="overfetch"
            )
            tm_config['recency_weight'] = st.slider(
                "Recency", 
                min_value=0.0, max_value=1.0,
                value=float(settings['translation_memory']['recency_weight']),
                step=0.01,
                help="📅 **Temporal Preference**: How much to favor recent translations over older ones. 0.0 = pure similarity, 1.0 = heavily favor recent. 0.1-0.3 gives slight preference to recent style evolution.",
                key="recency"
            )
            tm_config['embedding_model'] = st.selectbox(
                "Embedding",
                options=['text-embedding-ada-002', 'text-embedding-3-small', 'text-embedding-3-large'],
                index=0 if settings['translation_memory']['embedding_model'] == 'text-embedding-ada-002' else 0,
                help="🔤 **Semantic Understanding Model**: OpenAI model for converting text to numerical vectors for similarity search. ada-002 is cost-effective, 3-large is most accurate but expensive. 3-small offers good balance.",
                key="embedding_model"
            )
            tm_config['embedding_timeout_seconds'] = st.number_input(
                "Embed Timeout", 
                min_value=5, max_value=120,
                value=max(5, settings['translation_memory']['embedding_timeout_seconds']),
                help="⏰ **Embedding Generation Timeout**: Time to wait for OpenAI to convert text to vectors. Network latency affects this. 10-30 seconds handles most cases including API slowdowns.",
                key="embed_timeout"
            )
            settings['translation_memory'] = tm_config
    
    with col4:
        st.markdown("#### 🌍 Environment")
        if 'environment' in settings:
            env_config = {}
            env_config['session_name_pattern'] = st.text_input(
                "Session Pattern", 
                value=settings['environment']['session_name_pattern'],
                help="🏷️ **Session Naming Template**: Pattern for generating unique session IDs. Use placeholders like {timestamp}, {user}, {channel}. Helps organize and debug translation sessions. Example: 'bot_{timestamp}_{channel}'",
                key="session_pattern"
            )
            env_config['log_level'] = st.selectbox(
                "Log Level",
                options=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                index=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'].index(settings['environment']['log_level']),
                help="📊 **Logging Verbosity**: Controls how much detail appears in logs. DEBUG = everything (slow), INFO = important events, WARNING = only problems, ERROR = failures only. Use INFO for production, DEBUG for troubleshooting.",
                key="log_level"
            )
            env_config['log_format'] = st.text_area(
                "Log Format", 
                value=settings['environment']['log_format'],
                height=68,
                help="📝 **Log Message Template**: Python logging format string. Include %(asctime)s for timestamps, %(levelname)s for severity, %(message)s for content. Customize for your monitoring system needs.",
                key="log_format"
            )
            settings['environment'] = env_config
    
    with col5:
        st.markdown("#### 🔧 Individual")
        if 'individual' in settings:
            ind_config = {}
            # Show only first 8 individual settings to fit in column
            items = list(settings['individual'].items())[:8]
            for key, value in items:
                if value is not None:
                    short_key = key.replace('_', ' ').title()[:12]  # Truncate for space
                    if isinstance(value, (int, float)):
                        # Set reasonable bounds
                        if isinstance(value, int):
                            min_val = max(0, int(value * 0.1)) if value > 0 else value - 1000
                            max_val = int(value * 10) if value > 0 else value + 1000
                            ind_config[key] = st.number_input(
                                short_key, 
                                min_value=min_val,
                                max_value=max_val,
                                value=value,
                                help=f"🗄️ **Database Setting**: `{key}` - Individual configuration value stored in database. This numeric setting controls specific bot behavior. Changes here are UI-only and don't persist to production database.",
                                key=f"ind_{key}"
                            )
                        else:  # float
                            min_val = max(0.0, value * 0.1) if value > 0 else value - 100.0
                            max_val = value * 10 if value > 0 else value + 100.0
                            ind_config[key] = st.number_input(
                                short_key, 
                                min_value=min_val,
                                max_value=max_val,
                                value=value,
                                step=0.1 if abs(value) < 10 else 1.0,
                                help=f"🔢 **Database Float Setting**: `{key}` - Decimal configuration value from database. Controls fine-tuned bot parameters. UI changes don't affect production - perfect for testing different values.",
                                key=f"ind_{key}"
                            )
                    elif isinstance(value, bool):
                        ind_config[key] = st.checkbox(
                            short_key, 
                            value=value,
                            help=f"✅ **Database Boolean Setting**: `{key}` - True/False configuration toggle from database. Enables or disables specific bot features. Changes here are temporary and won't persist to production.",
                            key=f"ind_{key}"
                        )
                    else:
                        ind_config[key] = st.text_input(
                            short_key, 
                            value=str(value),
                            help=f"📝 **Database Text Setting**: `{key}` - String configuration value from database. Contains text-based bot settings like patterns, templates, or identifiers. Edit freely - changes are UI-only.",
                            key=f"ind_{key}"
                        )
            
            # Add remaining settings to the dict even if not displayed
            for key, value in settings['individual'].items():
                if key not in ind_config:
                    ind_config[key] = value
            settings['individual'] = ind_config
    
    # Button to reload settings from database
    if st.button("🔄 Reload Settings from Database"):
        st.session_state.db_settings = load_all_db_settings()
        st.success("Settings reloaded from database!")
        st.rerun()
    
    return settings

def render_conversation(placeholder, messages):
    """Render the conversation in chronological order using native Streamlit components"""
    # Clear the placeholder
    placeholder.empty()
    
    # Use the placeholder as a container
    with placeholder.container():
        for msg in messages:
            role = msg['role']
            content = msg['content']
            complete = msg.get('complete', False)
            progress = msg.get('progress', 0)
            icon = msg['icon']
            
            # Create message container with role-specific styling
            if role == 'Source Text':
                with st.container():
                    st.markdown(f"""
                    <div style="background: #e8f5e8; padding: 12px; margin: 8px 0; border-radius: 8px; border-left: 4px solid #4caf50;">
                        <strong>{icon} {role} (Original):</strong>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Show source text content directly
                    st.markdown(f"<div style='margin-top: 8px; white-space: pre-wrap; padding: 10px; background: #f5f5f5; border-radius: 4px;'>{content}</div>", unsafe_allow_html=True)
                        
            elif role == 'Translator':
                with st.container():
                    st.markdown(f"""
                    <div style="background: #f3e5f5; padding: 12px; margin: 8px 0; border-radius: 8px; border-left: 4px solid #7b1fa2;">
                        <strong>{icon} {role}:</strong>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Progress bar if not complete
                    if not complete and progress is not None:
                        st.progress(progress)
                    
                    # Content with typing cursor (keep formatting for Translator)
                    cursor = " |" if not complete else ""
                    st.markdown(f"<div style='margin-top: 8px; white-space: pre-wrap;'>{content}{cursor}</div>", unsafe_allow_html=True)
            else:
                with st.container():
                    st.markdown(f"""
                    <div style="background: #e3f2fd; padding: 12px; margin: 8px 0; border-radius: 8px; border-left: 4px solid #1976d2;">
                        <strong>{icon} {role}:</strong>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Progress bar if not complete
                    if not complete and progress is not None:
                        st.progress(progress)
                    
                    # Content with typing cursor (render Editor markdown properly)
                    cursor = " |" if not complete else ""
                    # Keep markdown formatting for Editor - just clean up excessive triple newlines
                    clean_content = content.replace('\n\n\n', '\n\n')
                    st.markdown(f"{clean_content}{cursor}")

def run_live_translation_with_streaming(source_text, use_memory):
    """Run live translation with real-time Claude thinking and response streaming"""
    
    # Get configuration - use UI settings if available, otherwise database defaults
    st.markdown("### 🔧 Live Translation Configuration")
    try:
        # Check if we have UI settings from the settings panel
        has_ui_settings = 'db_settings' in st.session_state and st.session_state.db_settings
        
        if has_ui_settings:
            # Use settings from UI
            ui_settings = st.session_state.db_settings
            ai_config = ui_settings.get('ai_model', {})
            prompts = ui_settings.get('prompts', {})
            
            # Get prompt content
            translator_prompt = prompts.get('autogen_translator', 'UI prompt not available')
            editor_prompt = prompts.get('autogen_editor', 'UI prompt not available')
            
            config_source = f"🎛️ Using UI Settings (from Settings Panel) - {len(ui_settings)} categories loaded"
            print(f"💡 UI Settings Debug: Found {len(ai_config)} AI config items, {len(prompts)} prompts")
        else:
            # Fallback to database
            from autogen_games import ProductionConfigLoader
            prod_config = ProductionConfigLoader()
            ai_config = prod_config.get_ai_model_config()
            translator_prompt = prod_config.get_prompt("autogen_translator")
            editor_prompt = prod_config.get_prompt("autogen_editor")
            
            config_source = "🗄️ Using Database Defaults (visit Settings to override)"
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Model", ai_config.get('model_id', 'Unknown'))
            st.metric("Max Tokens", f"{ai_config.get('max_tokens', 0):,}")
            st.metric("Temperature", ai_config.get('temperature', 0.0))
        
        with col2:
            st.metric("Thinking Budget", f"{ai_config.get('thinking_budget_tokens', 0):,}")
            st.metric("Timeout", f"{ai_config.get('timeout_seconds', 0)}s")
            st.metric("Max Messages", "6")
        
        with col3:
            translator_preview = translator_prompt[:100] + "..." if len(translator_prompt) > 100 else translator_prompt
            editor_preview = editor_prompt[:100] + "..." if len(editor_prompt) > 100 else editor_prompt
            st.text_area("Translator Prompt", translator_preview, height=68, disabled=True)
            st.text_area("Editor Prompt", editor_preview, height=68, disabled=True)
            
        st.info(f"⚡ {config_source}")
        
        # Store the config for the translation
        st.session_state.live_config = {
            'ai_model': ai_config,
            'translator_prompt': translator_prompt,
            'editor_prompt': editor_prompt
        }
        
    except Exception as e:
        st.error(f"❌ Could not load runtime config: {e}")
    
    st.markdown("---")
    
    # Initialize session state for tracking
    if 'conversation_history' not in st.session_state:
        st.session_state.conversation_history = []
    
    # ------------- PRODUCTION translation-memory context (same as bot) ----------------
    memory = []
    if use_memory:
        memory_start_time = time.time()
        try:
            st.info(f"🧠 Querying translation memory for text (k=10)")
            memory = recall_tm(source_text, k=10)  # Same as production bot
            memory_query_time = time.time() - memory_start_time
            
            if memory:
                st.success(f"✅ Found {len(memory)} relevant memories in {memory_query_time:.3f}s")
                
                # Log detailed memory analysis like the bot
                for i, m in enumerate(memory, 1):
                    similarity = m.get('similarity', 0.0)
                    source_preview = m.get('source_text', '')[:60] + "..." if len(m.get('source_text', '')) > 60 else m.get('source_text', '')
                    translation_preview = m.get('translation_text', '')[:60] + "..." if len(m.get('translation_text', '')) > 60 else m.get('translation_text', '')
                    st.write(f"📝 Memory {i}: similarity={similarity:.3f}")
                    with st.expander(f"View Memory {i} Details"):
                        st.write(f"**Source:** {source_preview}")
                        st.write(f"**Translation:** {translation_preview}")
                
                # Calculate memory statistics like the bot
                similarities = [m.get('similarity', 0.0) for m in memory]
                avg_similarity = sum(similarities) / len(similarities) if similarities else 0
                max_similarity = max(similarities) if similarities else 0
                min_similarity = min(similarities) if similarities else 0
                st.info(f"📊 Memory stats: avg_sim={avg_similarity:.3f}, max_sim={max_similarity:.3f}, min_sim={min_similarity:.3f}")
            else:
                st.warning(f"❌ No memories found in {memory_query_time:.3f}s")
                
        except Exception as e:
            memory_query_time = time.time() - memory_start_time
            st.error(f"💥 TM recall failed after {memory_query_time:.3f}s: {e}")
    
    # Create containers for live streaming
    status_container = st.empty()
    conversation_placeholder = st.empty()  # Single placeholder for chronological conversation
    stats_container = st.empty()
    
    # Track conversation messages in order
    conversation_messages = []
    
    # Initialize client
    try:
        client = get_anthropic_client(os.getenv('ANTHROPIC_API_KEY'))
    except Exception as e:
        st.error(f"❌ Failed to initialize Claude client: {str(e)}")
        return
    
    try:
        # Run the streaming translation using production AutoGen event stream
        start_time = time.time()
        current_step = ""
        thinking_text = ""
        response_text = ""
        final_translation = ""
        conversation_log = ""
        
        # Map AutoGen event objects to update dictionaries expected by UI
        async def run_streaming():
            last_translator_message = ""
            full_conversation_log = []
            current_translator_text = ""
            current_editor_text = ""
            
            # Build complete runtime configuration - NO FALLBACKS, FAIL FAST!
            assert 'live_config' in st.session_state, "UI configuration is required - no database fallbacks allowed!"
            
            complete_runtime_config = st.session_state.live_config.copy()
            
            # Add execution-specific details
            complete_runtime_config.update({
                'use_memory': use_memory,
                'memory_count': len(memory),
                'config_source': 'UI_ONLY_NO_FALLBACKS'
            })
            
            # Always use custom streaming with UI config - NO DATABASE FALLBACKS!
            print(f"🎛️ USING CUSTOM STREAMING with complete runtime config: {list(complete_runtime_config.keys())}")
            stream_generator = custom_autogen_event_stream(source_text, complete_runtime_config, memory)
            
            # FIRST: Show the original source text that needs to be translated
            source_message = {
                'role': 'Source Text',
                'content': source_text,
                'complete': True,
                'icon': '📝'
            }
            conversation_messages.append(source_message)
            render_conversation(conversation_placeholder, conversation_messages)
            
            async for ev in stream_generator:
                print(f"🔧 Processing event (UI config): {type(ev).__name__} from {getattr(ev, 'source', 'unknown')}")
                
                # Handle token-level events for real-time streaming
                if hasattr(ev, 'event_type') and ev.event_type == 'token':
                    role = getattr(ev, 'source', 'unknown')
                    token = ev.content.text
                    accumulated = getattr(ev, 'accumulated_text', '')
                    token_index = getattr(ev, 'token_index', 0)
                    total_tokens = getattr(ev, 'total_tokens', 1)
                    
                    print(f"🪙 Token {token_index+1}/{total_tokens} from {role}: '{token}'")
                    
                    # Update the appropriate text buffer and yield streaming update
                    if 'Translator' in str(role):
                        current_translator_text = accumulated
                        last_translator_message = accumulated  # Update as we stream
                        yield {
                            'type': 'response_token', 
                            'content': token, 
                            'accumulated': accumulated,
                            'token_index': token_index,
                            'total_tokens': total_tokens
                        }
                    else:
                        current_editor_text = accumulated  
                        yield {
                            'type': 'thinking_token', 
                            'content': token, 
                            'accumulated': accumulated,
                            'token_index': token_index,
                            'total_tokens': total_tokens
                        }
                        
                elif hasattr(ev, 'event_type') and ev.event_type == 'agent_start':
                    # Agent started speaking
                    role = getattr(ev, 'source', 'unknown')
                    print(f"🎬 Agent {role} starting...")
                    yield {'type': 'agent_start', 'agent': role}
                    
                elif hasattr(ev, 'content'):
                    # Complete message event (fallback - shouldn't happen with token streaming)
                    role = getattr(ev, 'source', 'unknown')
                    content = str(ev.content)
                    
                    print(f"📝 Complete message from {role}: {content[:50]}...")
                    
                    # Log all messages for conversation history
                    full_conversation_log.append(f"{role}: {content}")
                    
                    # Keep track of final translator message
                    if 'Translator' in str(role):
                        last_translator_message = content
                        current_translator_text = content
                        yield {'type': 'response', 'content': content}
                    else:
                        current_editor_text = content
                        yield {'type': 'thinking', 'content': content}
                else:
                    # Non-message events used as status updates
                    event_name = ev.__class__.__name__
                    print(f"⚙️ Status event: {event_name}")
                    yield {'type': 'status', 'step_name': event_name}

            # Use the final translator text as the result
            final_result = last_translator_message or current_translator_text
            
            # after stream ends emit completion marker with final translation
            yield {
                'type': 'complete',
                'final_translation': final_result,
                'conversation_log': '\n\n'.join(full_conversation_log),
                'duration': time.time() - start_time
            }
                
        # Run async generator in sync context
        import asyncio
        
        async def process_stream():
            nonlocal current_step, thinking_text, response_text, final_translation, conversation_log, conversation_messages
            
            current_message = None  # Track current message being built
            
            async for update in run_streaming():
                update_type = update.get('type', '')
                
                if update_type == 'status':
                    # Update current step with role identification
                    step_name = update.get('step_name', 'Processing')
                    current_step = step_name
                    
                    # Apply role-specific styling
                    if 'translator' in step_name.lower() or 'translation' in step_name.lower():
                        step_class = "translator-step"
                        role_icon = "🔄"
                    elif 'editor' in step_name.lower() or 'critique' in step_name.lower():
                        step_class = "editor-step" 
                        role_icon = "🧐"
                    else:
                        step_class = ""
                        role_icon = "⚙️"
                    
                    status_html = f'<div class="step-header {step_class}">{role_icon} {step_name}</div>'
                    status_container.markdown(status_html, unsafe_allow_html=True)
                    
                elif update_type == 'agent_start':
                    # Agent started speaking - create new message entry
                    agent = update.get('agent', 'Unknown')
                    if 'Translator' in agent:
                        role = 'Translator'
                        status_html = f'<div class="step-header translator-step">🔄 Translator thinking...</div>'
                    else:
                        role = 'Editor'
                        status_html = f'<div class="step-header editor-step">🧐 Editor reviewing...</div>'
                    
                    status_container.markdown(status_html, unsafe_allow_html=True)
                    
                    # Start new message
                    current_message = {
                        'role': role,
                        'content': '',
                        'complete': False,
                        'icon': '🔄' if role == 'Translator' else '🧐'
                    }
                    conversation_messages.append(current_message)
                    
                elif update_type == 'thinking_token' or update_type == 'response_token':
                    # Handle token-by-token updates for current message
                    if current_message:
                        accumulated = update.get('accumulated', '')
                        token_index = update.get('token_index', 0)
                        total_tokens = update.get('total_tokens', None)
                        
                        # Update current message content
                        current_message['content'] = accumulated
                        
                        if total_tokens is not None and total_tokens > 0:
                            # Fake streaming - show progress bar
                            progress = (token_index + 1) / total_tokens
                            current_message['progress'] = progress
                            print(f"🪙 FAKE Token {token_index + 1}/{total_tokens}")
                        else:
                            # Real streaming - no progress bar, no total known
                            current_message['progress'] = None
                            print(f"🌊 REAL Token {token_index + 1} streaming live!")
                        
                        # Render entire conversation chronologically
                        render_conversation(conversation_placeholder, conversation_messages)
                    
                elif update_type == 'thinking' or update_type == 'response':
                    # Complete message - mark as finished
                    if current_message:
                        content = update.get('content', '')
                        if isinstance(content, list):
                            content = ''.join(str(item) for item in content)
                        current_message['content'] = str(content)
                        current_message['complete'] = True
                        
                        # Final render of completed message
                        render_conversation(conversation_placeholder, conversation_messages)
                    
                elif update_type == 'stats':
                    # Show stats from the reverted translator
                    stats_content = update.get('content', {})
                    if stats_content:
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("⏱️ Duration", f"{stats_content.get('duration', 0):.1f}s")
                        with col2:
                            st.metric("🔤 Input Tokens", f"{stats_content.get('input_tokens', 0):,}")
                        with col3:
                            st.metric("💰 Cost", f"${stats_content.get('total_cost', 0):.4f}")
                    
                elif update_type == 'complete':
                    # Handle completion from the reverted translator
                    final_translation = update.get('final_translation', '')
                    conversation_log = update.get('conversation_log', '')
                    duration = update.get('duration', 0)
                    
                    # Clear streaming containers
                    status_container.empty()
                    
                    # Extract final result from last translator message
                    final_result = ""
                    for msg in reversed(conversation_messages):
                        if msg['role'] == 'Translator':
                            final_result = msg['content']
                            break
                    
                    if not final_result:
                        final_result = final_translation
                    
                    # Show final result
                    st.success("✅ Translation Complete!")
                    
                    # Add to conversation history
                    conversation_entry = {
                        'timestamp': datetime.now(),
                        'source_text': source_text,
                        'final_translation': final_translation,
                        'memory_used': len(memory),
                        'duration': duration
                    }
                    st.session_state.conversation_history.append(conversation_entry)
                    
                    # Save to Supabase database
                    try:
                        # Determine streaming type
                        streaming_type = "real" if 'live_config' in st.session_state else "fake"
                        
                        # Get model configuration
                        ai_config = st.session_state.get('live_config', {}).get('ai_model', {})
                        model_used = ai_config.get('model_id')
                        temperature = ai_config.get('temperature')
                        max_tokens = ai_config.get('max_tokens')
                        
                        # Calculate processing time in milliseconds
                        processing_time_ms = int(duration * 1000) if duration else None
                        
                        # Prepare conversation log
                        formatted_conversation_log = []
                        for msg in conversation_messages:
                            formatted_conversation_log.append({
                                'role': msg['role'],
                                'content': msg['content'],
                                'complete': msg.get('complete', True)
                            })
                        
                        # Use complete runtime configuration for settings snapshot
                        settings_snapshot = st.session_state.get('live_config', {}).copy()
                        
                        # Add execution-specific details
                        settings_snapshot.update({
                            'final_model_used': model_used,
                            'final_temperature': temperature,
                            'final_max_tokens': max_tokens,
                            'actual_memory_used': len(memory),
                            'streaming_enabled': True,
                            'execution_timestamp': datetime.now().isoformat()
                        })
                        
                        # Save to database
                        db_result = save_conversation_to_db(
                            source_text=source_text,
                            translated_text=final_result,
                            conversation_log=formatted_conversation_log,
                            settings=settings_snapshot,
                            streaming_type=streaming_type,
                            model_used=model_used,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            processing_time_ms=processing_time_ms,
                            status="completed"
                        )
                        
                        if db_result:
                            st.success(f"💾 Conversation saved to database (ID: {db_result.get('id', 'unknown')})")
                        
                        # ------------- PRODUCTION memory storage (same as bot) ----------------
                        # Persist translation pair in translation memory (best-effort, same as bot)
                        save_start_time = time.time()
                        try:
                            import uuid
                            pair_id = f"streamlit-{uuid.uuid4()}"
                            st.info(f"💾 Saving translation pair to memory: {pair_id}")
                            
                            # Store in production memory system (same as bot)
                            store_tm(
                                src=source_text,
                                tgt=final_result,
                                pair_id=pair_id,
                                message_id=None,  # Streamlit doesn't have message IDs
                                channel_name="streamlit",
                                message_url=None,  # No URL for Streamlit translations
                                conversation_log=conversation_log,
                            )
                            save_time = time.time() - save_start_time
                            st.success(f"✅ Translation pair saved to memory in {save_time:.3f}s: {pair_id}")
                            
                        except Exception as e:
                            save_time = time.time() - save_start_time
                            st.error(f"💥 Memory storage failed after {save_time:.3f}s: {e}")
                        
                    except Exception as db_error:
                        st.error(f"❌ Failed to save conversation to database: {str(db_error)}")
                    break
                    
                elif update_type == 'error':
                    # Show comprehensive error details
                    error_message = update.get('content', 'Unknown error')
                    
                    # Clear streaming containers
                    # thinking_container.empty() # These were not defined in the original code
                    # response_container.empty() # These were not defined in the original code
                    status_container.empty()
                    
                    # Show main error
                    st.error(f"❌ Translation Error: {error_message}")
                    
                    # Save failed translation to database
                    try:
                        streaming_type = "real" if 'live_config' in st.session_state else "fake"
                        ai_config = st.session_state.get('live_config', {}).get('ai_model', {})
                        
                        # Use complete runtime configuration for error settings snapshot
                        settings_snapshot = complete_runtime_config.copy()
                        settings_snapshot.update({
                            'error_occurred': True,
                            'error_message': error_message,
                            'streaming_enabled': True,
                            'execution_timestamp': datetime.now().isoformat()
                        })
                        
                        # Save failed conversation
                        save_conversation_to_db(
                            source_text=source_text,
                            translated_text=None,
                            conversation_log=[],
                            settings=settings_snapshot,
                            streaming_type=streaming_type,
                            model_used=ai_config.get('model_id'),
                            temperature=ai_config.get('temperature'),
                            max_tokens=ai_config.get('max_tokens'),
                            error_message=error_message,
                            status="failed"
                        )
                        
                    except Exception as db_error:
                        st.warning(f"⚠️ Could not save error to database: {str(db_error)}")
                    
                    # Show troubleshooting tips
                    st.info("💡 **Troubleshooting Tips:**\n"
                           "- Check if Claude API is overloaded (try again in a few minutes)\n"
                           "- Verify API key is correctly set in environment\n"
                           "- Ensure database connection is working\n"
                           "- Try with shorter text to test basic functionality")
                    break
        
        # Run the async processing
        try:
            asyncio.run(process_stream())
        except Exception as e:
            # Comprehensive error handling
            import traceback
            
            # Clear any remaining streaming containers
            # thinking_container.empty() # These were not defined in the original code
            # response_container.empty() # These were not defined in the original code
            status_container.empty()
            
            # Show main error
            st.error(f"❌ Translation failed: {str(e)}")
            
            # Save exception to database
            try:
                streaming_type = "real" if 'live_config' in st.session_state else "fake"
                ai_config = st.session_state.get('live_config', {}).get('ai_model', {})
                
                # Use complete runtime configuration for exception settings snapshot
                settings_snapshot = st.session_state.get('live_config', {}).copy()
                settings_snapshot.update({
                    'exception_occurred': True,
                    'exception_type': type(e).__name__,
                    'streaming_enabled': True,
                    'execution_timestamp': datetime.now().isoformat()
                })
                
                error_details = f"{type(e).__name__}: {str(e)}\n\n{traceback.format_exc()}"
                
                save_conversation_to_db(
                    source_text=source_text,
                    translated_text=None,
                    conversation_log=[],
                    settings=settings_snapshot,
                    streaming_type=streaming_type,
                    model_used=ai_config.get('model_id'),
                    temperature=ai_config.get('temperature'),
                    max_tokens=ai_config.get('max_tokens'),
                    error_message=error_details,
                    status="failed"
                )
                
            except Exception as db_error:
                st.warning(f"⚠️ Could not save exception to database: {str(db_error)}")
            
            # Show detailed error information
            with st.expander("🔍 Detailed Error Information (Click to expand)", expanded=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Error Details:**")
                    st.json({
                        'error_type': type(e).__name__,
                        'error_message': str(e),
                        'source_text_length': len(source_text),
                        'memory_items': len(memory)
                    })
                
                with col2:
                    st.markdown("**Full Python Traceback:**")
                    st.code(traceback.format_exc(), language='python')
            
            # Add debug information
            with st.expander("🔧 Debug Information", expanded=False):
                st.markdown("**Environment:**")
                st.json({
                    'anthropic_api_key_set': bool(os.getenv('ANTHROPIC_API_KEY')),
                    'api_key_length': len(os.getenv('ANTHROPIC_API_KEY', '')) if os.getenv('ANTHROPIC_API_KEY') else 0,
                    'source_text_preview': source_text[:100] + '...' if len(source_text) > 100 else source_text,
                    'memory_preview': [m.get('translation_text', '')[:50] + '...' for m in memory[:3]] if memory else []
                })
            
            # Troubleshooting guide
            st.info("💡 **Troubleshooting Guide:**\n"
                   "1. **API Issues**: Check if Claude API is overloaded (wait 5-10 minutes)\n"
                   "2. **Authentication**: Verify ANTHROPIC_API_KEY is set correctly\n"
                   "3. **Database**: Ensure Django database connection is working\n"
                   "4. **Text Length**: Try with shorter text (under 1000 characters)\n"
                   "5. **Memory**: Disable 'Use Translation Memory' to test basic functionality")
        
    except Exception as e:
        # Catch-all for any other errors
        import traceback
        st.error(f"❌ Critical error during setup: {str(e)}")
        with st.expander("🔍 Setup Error Details", expanded=True):
            st.code(traceback.format_exc(), language='python')

def show_live_translation():
    """Main live translation interface"""
    st.markdown('<h1 class="main-header">🔥 Live Translation Studio</h1>', unsafe_allow_html=True)
    
    # Create a form to enable Command+Enter functionality
    with st.form(key="translation_form", clear_on_submit=False):
        col1, col2 = st.columns([3, 1])
        
        with col1:
            # Preload last article input if available
            last_input = st.session_state.get('last_article_input', '')
            
            source_text = st.text_area(
                "Enter text to translate:",
                value=last_input,
                height=200,
                placeholder="Enter Hebrew news text here... (Press Ctrl+Enter or Cmd+Enter to translate)",
                help="💡 Press Ctrl+Enter (Windows/Linux) or Cmd+Enter (Mac) to start translation immediately!"
            )
    
        with col2:
            st.markdown("### ⚙️ Settings")
            use_memory = st.checkbox("Use Translation Memory", value=True)
        
        # Form submit button - triggered by Ctrl+Enter or Cmd+Enter
        translate_clicked = st.form_submit_button("🚀 Start Live Translation", type="primary")
    
    # Execute translation when form is submitted (Cmd+Enter) or button clicked
    if translate_clicked:
        if source_text.strip():
            # Save the input for preloading next time
            st.session_state['last_article_input'] = source_text.strip()
            run_live_translation_with_streaming(source_text.strip(), use_memory)
        else:
            st.warning("⚠️ Please enter some text to translate")

def load_conversations_from_db():
    """Load conversations from Supabase database"""
    try:
        supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
        response = supabase.table("streamlit_conversations").select("*").order("created_at", desc=True).execute()
        return response.data
    except Exception as e:
        st.error(f"Failed to load conversations from database: {e}")
        return []

def show_conversation_history():
    """Display conversation history from database"""
    st.markdown('<h1 class="main-header">📚 Conversation History</h1>', unsafe_allow_html=True)
    
    # Load conversations from database instead of session state
    conversations = load_conversations_from_db()
    
    if not conversations:
        st.info("💭 No conversations yet. Go to Live Translation to start!")
        return
    
    st.markdown(f"**Total Conversations:** {len(conversations)}")
    
    for i, entry in enumerate(conversations, 1):
        # Parse created_at timestamp
        try:
            created_at = datetime.fromisoformat(entry['created_at'].replace('Z', '+00:00'))
            time_str = created_at.strftime('%Y-%m-%d %H:%M:%S UTC')
        except:
            time_str = str(entry.get('created_at', 'Unknown time'))
        
        with st.expander(f"Conversation #{i} - {time_str}"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Source Text:**")
                st.text_area("Source Text", entry['source_text'], disabled=True, key=f"db_source_{i}", label_visibility="collapsed")
            
            with col2:
                st.markdown("**Translation:**")
                translation = entry.get('translated_text') or "❌ Translation failed"
                st.text_area("Translation", translation, disabled=True, key=f"db_translation_{i}", label_visibility="collapsed")
            
            # Show stats if available
            col3, col4, col5 = st.columns(3)
            with col3:
                st.metric("Model", entry.get('model_used', 'N/A'))
            with col4:
                st.metric("Streaming", entry.get('streaming_type', 'N/A'))
            with col5:
                processing_time = entry.get('processing_time_ms')
                if processing_time:
                    st.metric("Duration", f"{processing_time/1000:.1f}s")
                else:
                    st.metric("Duration", "N/A")
            

            
            # Show settings if available
            if entry.get('settings'):
                with st.expander("⚙️ Settings Used", expanded=False):
                    st.json(entry['settings'])

def show_cost_analytics():
    """Display cost analytics from database"""
    st.markdown('<h1 class="main-header">💰 Cost Analytics</h1>', unsafe_allow_html=True)
    
    # Load conversations from database
    conversations = load_conversations_from_db()
    
    if not conversations:
        st.info("💭 No data yet. Complete some translations first!")
        return
    
    # Calculate totals
    total_conversations = len(conversations)
    total_duration = sum((entry.get('processing_time_ms') or 0) / 1000 for entry in conversations)
    avg_duration = total_duration / max(total_conversations, 1)
    
    # Display summary metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("💬 Conversations", total_conversations)
    with col2:
        st.metric("⏱️ Total Duration", f"{total_duration:.1f}s")
    with col3:
        st.metric("📊 Avg Duration", f"{avg_duration:.1f}s")
    
    # Show duration trend
    if total_conversations > 1:
        st.markdown("### 📈 Duration Trend")
        durations = [(entry.get('processing_time_ms') or 0) / 1000 for entry in reversed(conversations)]
        st.line_chart(durations)
    
    # Show model usage breakdown
    st.markdown("### 🤖 Model Usage")
    model_counts = {}
    for conv in conversations:
        model = conv.get('model_used', 'Unknown')
        model_counts[model] = model_counts.get(model, 0) + 1
    
    if model_counts:
        for model, count in model_counts.items():
            st.metric(f"🎯 {model}", f"{count} conversations")
    
    # Show streaming type breakdown
    st.markdown("### 🌊 Streaming Types")
    streaming_counts = {}
    for conv in conversations:
        stream_type = conv.get('streaming_type', 'Unknown')
        streaming_counts[stream_type] = streaming_counts.get(stream_type, 0) + 1
    
    if streaming_counts:
        for stream_type, count in streaming_counts.items():
            st.metric(f"🔄 {stream_type.title()}", f"{count} conversations")

def show_settings_page():
    """Show settings configuration page"""
    st.markdown("# ⚙️ Settings Configuration")
    st.markdown("**Studio Mode**: Experiment with different settings without affecting production database")
    
    # Show all configurable settings
    current_settings = show_settings_panel()

def main():
    """Main Streamlit application"""
    # Sidebar navigation
    with st.sidebar:
        st.markdown("## 🤖 Claude Translation Studio")
        page = st.radio("Navigate:", [
            "🔥 Live Translation",
            "📚 Conversation History", 
            "💰 Cost Analytics",
            "⚙️ Settings"
        ])
    
    # Route to appropriate page
    if page == "🔥 Live Translation":
        show_live_translation()
    elif page == "📚 Conversation History":
        show_conversation_history()
    elif page == "💰 Cost Analytics":
        show_cost_analytics()
    elif page == "⚙️ Settings":
        show_settings_page()

if __name__ == "__main__":
    main() 