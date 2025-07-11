import streamlit as st
import asyncio
import os
import time
from datetime import datetime
import json
from app.translator import get_anthropic_client
from app.config_loader import get_config_loader

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
    background: #f8f9fa;
    padding: 1rem;
    border-left: 4px solid #FF6B35;
    border-radius: 8px;
    font-family: 'Courier New', monospace;
    font-size: 14px;
    margin: 1rem 0;
    white-space: pre-wrap;
    line-height: 1.4;
}

.response-box {
    background: #e8f4fd;
    padding: 1rem;
    border-left: 4px solid #1f77b4;
    border-radius: 8px;
    margin: 1rem 0;
    line-height: 1.6;
}

.conversation-step {
    border: 1px solid #ddd;
    border-radius: 10px;
    padding: 1rem;
    margin: 1rem 0;
    background: white;
}

.step-header {
    font-weight: bold;
    color: #333;
    margin-bottom: 0.5rem;
}

.thinking-header {
    color: #FF6B35;
    font-weight: bold;
    font-size: 16px;
    margin-bottom: 0.5rem;
    display: flex;
    align-items: center;
}

.response-header {
    color: #1f77b4;
    font-weight: bold;
    font-size: 16px;
    margin-bottom: 0.5rem;
    display: flex;
    align-items: center;
}

.streaming-container {
    border: 1px solid #e0e0e0;
    border-radius: 10px;
    margin: 1rem 0;
    overflow: hidden;
}

.streaming-header {
    background: #f5f5f5;
    padding: 0.8rem;
    border-bottom: 1px solid #e0e0e0;
    font-weight: bold;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.streaming-content {
    padding: 1rem;
    max-height: 400px;
    overflow-y: auto;
    font-family: 'Courier New', monospace;
    font-size: 14px;
    line-height: 1.4;
    background: white;
}
</style>
""", unsafe_allow_html=True)

def main():
    st.markdown('<h1 class="main-header">🤖 Claude Translation Studio</h1>', unsafe_allow_html=True)
    st.markdown("**Real-time AI conversation viewer with Claude's thinking process**")
    
    # Sidebar for settings
    with st.sidebar:
        st.header("⚙️ Settings")
        
        # API Key check
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if api_key:
            st.success("✅ Claude API Key loaded")
        else:
            st.error("❌ No Claude API Key found")
            st.stop()
            
        # Model info
        try:
            config = get_config_loader()
            ai_config = config.get_ai_model_config()
            st.info(f"📋 Model: {ai_config['model_id']}")
            st.info(f"🎯 Max Tokens: {ai_config['max_tokens']:,}")
            st.info(f"🌡️ Temperature: {ai_config['temperature']}")
        except Exception as e:
            st.error(f"Config error: {e}")
    
    # Main content tabs
    tab1, tab2, tab3 = st.tabs(["🚀 Live Translation", "📊 Conversation History", "💰 Cost Analytics"])
    
    with tab1:
        st.header("🚀 Live Translation with Claude's Thinking Process")
        
        # Input form
        with st.form("translation_form"):
            source_text = st.text_area(
                "Enter text to translate:",
                placeholder="Breaking news: Tech billionaire announces major acquisition...",
                height=150
            )
            
            # Memory simulation
            use_memory = st.checkbox("Simulate previous translations (for context)")
            
            submitted = st.form_submit_button("🔥 Start Translation", type="primary")
        
        if submitted and source_text.strip():
            run_live_translation_with_streaming(source_text, use_memory)
    
    with tab2:
        st.header("📊 Conversation History")
        show_conversation_history()
    
    with tab3:
        st.header("💰 Cost Analytics")
        show_cost_analytics()

def run_live_translation_with_streaming(source_text, use_memory):
    """Run live translation with real-time thinking and response streaming"""
    
    # Initialize session state for tracking
    if 'conversation_history' not in st.session_state:
        st.session_state.conversation_history = []
    
    # Prepare memory
    memory = []
    if use_memory:
        memory = [
            {
                'translation_text': '🇺🇸 Трамп выиграл выборы. Либералы в шоке',
                'message_url': 'https://t.me/test/123'
            },
            {
                'translation_text': '🇮🇱 Нетаньяху встретился с Байденом',
                'message_url': 'https://t.me/test/124'
            }
        ]
    
    # Create containers for streaming
    status_container = st.empty()
    
    # Main streaming area
    st.markdown("### 🔄 Claude's Editorial Process")
    
    # Start translation
    start_time = time.time()
    conversation_log = ""
    final_translation = ""
    
    try:
        client = get_anthropic_client(os.getenv('ANTHROPIC_API_KEY'))
        
        # Run streaming translation
        for step in stream_translation_process(client, source_text, memory):
            if step['type'] == 'thinking':
                display_thinking_stream(step['content'], step['step_name'])
            elif step['type'] == 'response':
                final_translation = display_response_stream(step['content'], step['step_name'])
            elif step['type'] == 'status':
                with status_container:
                    st.info(f"🔄 {step['content']}")
            elif step['type'] == 'complete':
                conversation_log = step['conversation_log']
                final_translation = step['final_translation']
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Final status
        with status_container:
            st.success(f"✅ Translation completed in {duration:.1f}s")
        
        # Display final stats
        display_translation_stats(source_text, final_translation, duration, memory)
        
        # Save to history
        save_to_history(source_text, final_translation, conversation_log, duration)
        
    except Exception as e:
        with status_container:
            st.error(f"❌ Translation failed: {str(e)}")

def stream_translation_process(client, source_text, memory):
    """Generator that yields streaming updates from the translation process"""
    
    # Simulate the editorial process with real API calls
    import asyncio
    from app.translator import translate_and_link_streaming
    
    # Create event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Run the streaming translation
        async_gen = translate_and_link_streaming(client, source_text, memory)
        
        conversation_log = ""
        final_translation = ""
        
        # Convert async generator to sync
        while True:
            try:
                step = loop.run_until_complete(async_gen.__anext__())
                
                if step['type'] == 'complete':
                    conversation_log = step['conversation_log']
                    final_translation = step['final_translation']
                
                yield step
                
                if step['type'] == 'complete':
                    break
                    
            except StopAsyncIteration:
                break
                
    finally:
        loop.close()

def display_thinking_stream(content_generator, step_name):
    """Display thinking process with streaming effect"""
    
    # Create container for this thinking step
    with st.container():
        st.markdown(f"""
        <div class="streaming-container">
            <div class="streaming-header">
                🧠 Claude is thinking: {step_name}
            </div>
            <div class="streaming-content" id="thinking-content">
        """, unsafe_allow_html=True)
        
        # Stream the thinking content
        thinking_placeholder = st.empty()
        accumulated_thinking = ""
        
        if hasattr(content_generator, '__iter__'):
            # If it's an iterable of chunks
            for chunk in content_generator:
                accumulated_thinking += chunk
                with thinking_placeholder:
                    st.markdown(f'<div class="thinking-box">{accumulated_thinking}</div>', 
                              unsafe_allow_html=True)
                time.sleep(0.02)  # Small delay for visual effect
        else:
            # If it's a single string, simulate streaming
            for char in content_generator:
                accumulated_thinking += char
                with thinking_placeholder:
                    st.markdown(f'<div class="thinking-box">{accumulated_thinking}</div>', 
                              unsafe_allow_html=True)
                time.sleep(0.01)
        
        st.markdown("</div></div>", unsafe_allow_html=True)

def display_response_stream(content_generator, step_name):
    """Display response with streaming effect"""
    
    # Create container for this response step
    with st.container():
        st.markdown(f"""
        <div class="streaming-container">
            <div class="streaming-header">
                💬 Claude's response: {step_name}
            </div>
            <div class="streaming-content">
        """, unsafe_allow_html=True)
        
        # Use st.write_stream for natural streaming
        if hasattr(content_generator, '__iter__'):
            response = st.write_stream(content_generator)
        else:
            # Fallback for single strings
            response = st.write_stream(char for char in content_generator)
        
        st.markdown("</div></div>", unsafe_allow_html=True)
        
        return response

def parse_conversation_log(conversation_log):
    """Parse conversation log into structured steps"""
    steps = []
    if not conversation_log:
        return steps
    
    lines = conversation_log.split('\n\n')
    
    for line in lines:
        if line.strip():
            if line.startswith('ПЕРЕВОД v1:'):
                steps.append({
                    'type': 'translation',
                    'version': 1,
                    'content': line.replace('ПЕРЕВОД v1: ', '').strip()
                })
            elif line.startswith('РЕДАКТОР'):
                steps.append({
                    'type': 'critique',
                    'content': line.split('): ', 1)[1].strip() if '): ' in line else line.strip()
                })
            elif line.startswith('ПЕРЕВОД v'):
                version = line.split('v')[1].split(':')[0]
                steps.append({
                    'type': 'revision',
                    'version': int(version),
                    'content': line.split(': ', 1)[1].strip() if ': ' in line else line.strip()
                })
    
    return steps

def display_conversation_flow(steps, final_translation):
    """Display the conversation flow in a beautiful format"""
    st.markdown("### 🔄 Editorial Conversation Flow")
    
    for i, step in enumerate(steps):
        if step['type'] == 'translation':
            st.markdown(f"""
            <div class="conversation-step">
                <div class="step-header">📝 Initial Translation (v{step['version']})</div>
                <div class="response-box">{step['content']}</div>
            </div>
            """, unsafe_allow_html=True)
            
        elif step['type'] == 'critique':
            st.markdown(f"""
            <div class="conversation-step">
                <div class="step-header">🔍 Editor Critique</div>
                <div class="thinking-box">{step['content']}</div>
            </div>
            """, unsafe_allow_html=True)
            
        elif step['type'] == 'revision':
            st.markdown(f"""
            <div class="conversation-step">
                <div class="step-header">✨ Revised Translation (v{step['version']})</div>
                <div class="response-box">{step['content']}</div>
            </div>
            """, unsafe_allow_html=True)
    
    # Final result
    st.markdown("### 🎯 Final Result")
    st.success(f"**Final Translation:** {final_translation}")

def display_translation_stats(source_text, final_translation, duration, memory):
    """Display comprehensive translation statistics"""
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("⏱️ Duration", f"{duration:.1f}s")
    
    with col2:
        st.metric("📝 Source Length", f"{len(source_text)} chars")
    
    with col3:
        st.metric("📤 Output Length", f"{len(final_translation)} chars")
    
    with col4:
        st.metric("🧠 Memory Items", len(memory))
    
    # Cost estimation (simplified)
    est_input_tokens = len(source_text) * 1.3  # Rough estimate
    est_output_tokens = len(final_translation) * 1.3
    est_cost = (est_input_tokens / 1_000_000 * 3.0) + (est_output_tokens / 1_000_000 * 15.0)
    
    st.markdown(f"""
    <div class="cost-box">
        <h4>💰 Estimated Cost Breakdown</h4>
        <p>📥 Input: ~{est_input_tokens:.0f} tokens</p>
        <p>📤 Output: ~{est_output_tokens:.0f} tokens</p>
        <p>💵 Total Cost: ~${est_cost:.4f}</p>
    </div>
    """, unsafe_allow_html=True)

def save_to_history(source_text, final_translation, conversation_log, duration):
    """Save translation to session history"""
    if 'conversation_history' not in st.session_state:
        st.session_state.conversation_history = []
    
    entry = {
        'timestamp': datetime.now().isoformat(),
        'source_text': source_text,
        'final_translation': final_translation,
        'conversation_log': conversation_log,
        'duration': duration
    }
    
    st.session_state.conversation_history.insert(0, entry)
    
    # Keep only last 10 entries
    if len(st.session_state.conversation_history) > 10:
        st.session_state.conversation_history = st.session_state.conversation_history[:10]

def show_conversation_history():
    """Display conversation history"""
    if 'conversation_history' not in st.session_state or not st.session_state.conversation_history:
        st.info("📝 No conversation history yet. Run some translations to see them here!")
        return
    
    st.write(f"**Showing {len(st.session_state.conversation_history)} recent translations:**")
    
    for i, entry in enumerate(st.session_state.conversation_history):
        with st.expander(f"🔍 Translation #{i+1} - {entry['timestamp'][:19]}"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**📥 Source Text:**")
                st.text_area("", entry['source_text'], disabled=True, key=f"source_{i}")
            
            with col2:
                st.markdown("**📤 Final Translation:**")
                st.text_area("", entry['final_translation'], disabled=True, key=f"translation_{i}")
            
            st.markdown(f"**⏱️ Duration:** {entry['duration']:.1f}s")
            
            if st.button(f"Show Full Conversation", key=f"show_conv_{i}"):
                st.text_area("Full Conversation Log:", entry['conversation_log'], height=300, disabled=True)

def show_cost_analytics():
    """Display cost analytics"""
    if 'conversation_history' not in st.session_state or not st.session_state.conversation_history:
        st.info("💰 No cost data yet. Run some translations to see analytics!")
        return
    
    # Calculate total stats
    total_translations = len(st.session_state.conversation_history)
    total_duration = sum(entry['duration'] for entry in st.session_state.conversation_history)
    avg_duration = total_duration / total_translations
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("📊 Total Translations", total_translations)
    
    with col2:
        st.metric("⏱️ Total Time", f"{total_duration:.1f}s")
    
    with col3:
        st.metric("📈 Avg Duration", f"{avg_duration:.1f}s")
    
    # Estimated costs
    total_chars_in = sum(len(entry['source_text']) for entry in st.session_state.conversation_history)
    total_chars_out = sum(len(entry['final_translation']) for entry in st.session_state.conversation_history)
    
    est_total_cost = (total_chars_in * 1.3 / 1_000_000 * 3.0) + (total_chars_out * 1.3 / 1_000_000 * 15.0)
    
    st.markdown(f"""
    <div class="cost-box">
        <h4>💰 Session Cost Summary</h4>
        <p>📝 Characters Processed: {total_chars_in + total_chars_out:,}</p>
        <p>💵 Estimated Total Cost: ${est_total_cost:.4f}</p>
        <p>📊 Cost per Translation: ${est_total_cost/total_translations:.4f}</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main() 