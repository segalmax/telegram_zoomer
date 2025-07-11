import streamlit as st
import asyncio
import os
import time
from datetime import datetime
import json
from app.translator import get_anthropic_client
from app.config_loader import get_config_loader
from app.vector_store import recall  # Import for real memory data

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

def run_live_translation_with_streaming(source_text, use_memory):
    """Run live translation with real-time Claude thinking and response streaming"""
    
    # Initialize session state for tracking
    if 'conversation_history' not in st.session_state:
        st.session_state.conversation_history = []
    
    # Prepare memory from real database
    memory = []
    if use_memory:
        try:
            # Get real translation memory from database using vector similarity
            config = get_config_loader()
            k = int(config.get_setting('DEFAULT_RECALL_K'))
            memory = recall(source_text, k=k)
            
            # Display memory entries
            show_memory_entries(memory)
            
        except Exception as e:
            st.error(f"❌ Error loading memory: {str(e)}")
    
    # Create containers for live streaming
    status_container = st.empty()
    thinking_container = st.empty()
    response_container = st.empty()
    stats_container = st.empty()
    
    # Initialize client
    try:
        client = get_anthropic_client(os.getenv('ANTHROPIC_API_KEY'))
    except Exception as e:
        st.error(f"❌ Failed to initialize Claude client: {str(e)}")
        return

    # Import the streaming function
    from app.translator import translate_and_link_streaming
    
    try:
        # Run the streaming translation - NOTE: removed ai_config parameter
        start_time = time.time()
        current_step = ""
        thinking_text = ""
        response_text = ""
        final_translation = ""
        conversation_log = ""
        
        # Create async generator - translate_and_link_streaming no longer takes ai_config
        async def run_streaming():
            async for update in translate_and_link_streaming(client, source_text, memory):
                yield update
                
        # Run async generator in sync context
        import asyncio
        
        async def process_stream():
            nonlocal current_step, thinking_text, response_text, final_translation, conversation_log
            
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
                    
                elif update_type == 'thinking':
                    # Handle thinking content - the reverted code returns lists
                    content = update.get('content', '')
                    if isinstance(content, list):
                        content = ''.join(str(item) for item in content)
                    thinking_text += str(content)
                    thinking_html = f'<div class="thinking-box"><strong>💭 Thinking:</strong><br>{thinking_text}</div>'
                    thinking_container.markdown(thinking_html, unsafe_allow_html=True)
                    
                elif update_type == 'response':
                    # Handle response content - the reverted code returns lists
                    content = update.get('content', '')
                    if isinstance(content, list):
                        content = ''.join(str(item) for item in content)
                    response_text += str(content)
                    response_html = f'<div class="response-box"><strong>💬 Response:</strong><br>{response_text}</div>'
                    response_container.markdown(response_html, unsafe_allow_html=True)
                    
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
                    thinking_container.empty()
                    response_container.empty()
                    status_container.empty()
                    
                    # Show final result
                    st.success("✅ Translation Complete!")
                    st.markdown("### 🎯 Final Translation:")
                    st.text_area("Final Translation", final_translation, height=150, disabled=True, label_visibility="collapsed")
                    
                    # Show conversation log
                    if conversation_log:
                        with st.expander("📋 Translation Process Log"):
                            st.text_area("Conversation Log", conversation_log, height=200, disabled=True, label_visibility="collapsed")
                    
                    # Add to conversation history
                    conversation_entry = {
                        'timestamp': datetime.now(),
                        'source_text': source_text,
                        'final_translation': final_translation,
                        'memory_used': len(memory),
                        'duration': duration
                    }
                    st.session_state.conversation_history.append(conversation_entry)
                    break
                    
                elif update_type == 'error':
                    # Show comprehensive error details
                    error_message = update.get('content', 'Unknown error')
                    
                    # Clear streaming containers
                    thinking_container.empty()
                    response_container.empty()
                    status_container.empty()
                    
                    # Show main error
                    st.error(f"❌ Translation Error: {error_message}")
                    
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
            thinking_container.empty()
            response_container.empty()
            status_container.empty()
            
            # Show main error
            st.error(f"❌ Translation failed: {str(e)}")
            
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
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        source_text = st.text_area(
            "Enter text to translate:",
            height=200,
            placeholder="Enter Hebrew news text here..."
        )
    
    with col2:
        st.markdown("### ⚙️ Settings")
        use_memory = st.checkbox("Use Translation Memory", value=True)
        
        st.markdown("### 🎯 Quick Tests")
        if st.button("Test: Simple Text"):
            source_text = "שלום עולם"
            st.rerun()
        if st.button("Test: News Article"):
            source_text = "ישראל חתמה על הסכם שלום עם מדינה ערבית נוספת"
            st.rerun()
    
    if st.button("🚀 Start Live Translation", type="primary", disabled=not source_text.strip()):
        if source_text.strip():
            run_live_translation_with_streaming(source_text.strip(), use_memory)
        else:
            st.warning("⚠️ Please enter some text to translate")

def show_conversation_history():
    """Display conversation history"""
    st.markdown('<h1 class="main-header">📚 Conversation History</h1>', unsafe_allow_html=True)
    
    if 'conversation_history' not in st.session_state or not st.session_state.conversation_history:
        st.info("💭 No conversations yet. Go to Live Translation to start!")
        return
    
    st.markdown(f"**Total Conversations:** {len(st.session_state.conversation_history)}")
    
    for i, entry in enumerate(reversed(st.session_state.conversation_history), 1):
        with st.expander(f"Conversation #{len(st.session_state.conversation_history) - i + 1} - {entry['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Source Text:**")
                st.text_area("Source Text", entry['source_text'], disabled=True, key=f"source_{i}", label_visibility="collapsed")
            
            with col2:
                st.markdown("**Translation:**")
                st.text_area("Translation", entry['final_translation'], disabled=True, key=f"translation_{i}", label_visibility="collapsed")
            
            # Show stats if available
            col3, col4 = st.columns(2)
            with col3:
                st.metric("Memory Used", entry.get('memory_used', 0))
            with col4:
                st.metric("Duration", f"{entry.get('duration', 0):.1f}s")

def show_cost_analytics():
    """Display cost analytics"""
    st.markdown('<h1 class="main-header">💰 Cost Analytics</h1>', unsafe_allow_html=True)
    
    if 'conversation_history' not in st.session_state or not st.session_state.conversation_history:
        st.info("💭 No data yet. Complete some translations first!")
        return
    
    # Calculate totals
    total_conversations = len(st.session_state.conversation_history)
    total_duration = sum(entry.get('duration', 0) for entry in st.session_state.conversation_history)
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
        durations = [entry.get('duration', 0) for entry in st.session_state.conversation_history]
        st.line_chart(durations)

def main():
    """Main Streamlit application"""
    # Sidebar navigation
    with st.sidebar:
        st.markdown("## 🤖 Claude Translation Studio")
        page = st.radio("Navigate:", [
            "🔥 Live Translation",
            "📚 Conversation History", 
            "💰 Cost Analytics"
        ])
    
    # Route to appropriate page
    if page == "🔥 Live Translation":
        show_live_translation()
    elif page == "📚 Conversation History":
        show_conversation_history()
    elif page == "💰 Cost Analytics":
        show_cost_analytics()

if __name__ == "__main__":
    main() 