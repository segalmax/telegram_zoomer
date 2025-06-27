#!/usr/bin/env python3
"""
Test script for semantic translation with linking using Claude API
This script tests the new "do-it-in-one-prompt" approach.
"""

import os
import asyncio
import sys
from pathlib import Path
import logging
from datetime import datetime
from dotenv import load_dotenv
from app.translator import get_anthropic_client, translate_and_link

# Add the project root to Python path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_semantic_linking():
    """Test the new semantic linking approach"""
    
    # Test text about Iran and nuclear facilities
    test_text = """
    Iran announced today that it will increase uranium enrichment levels to 90% at the Natanz facility. 
    This development comes amid ongoing negotiations with European powers. Iranian officials stated that 
    the enrichment will take place at the underground Fordo facility near Isfahan.
    """
    
    # Mock memory data for semantic linking tests
    mock_memory = [
        {
            'translation_text': 'Иран снова угрожает увеличить обогащение урана до военного уровня',
            'message_url': 'https://t.me/rightnews/301'
        },
        {
            'translation_text': 'Европейские дипломаты пытаются спасти ядерную сделку с Ираном',
            'message_url': 'https://t.me/rightnews/285'
        },
        {
            'translation_text': 'Подземный завод в Фордо начал работу с новыми центрифугами',
            'message_url': 'https://t.me/rightnews/267'
        },
        {
            'translation_text': 'Израиль готовит удар по иранским ядерным объектам',
            'message_url': 'https://t.me/rightnews/199'
        },
        {
            'translation_text': 'Исфахан становится центром иранской ядерной программы',
            'message_url': 'https://t.me/rightnews/156'
        }
    ]
    
    # Initialize client
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("❌ ANTHROPIC_API_KEY not found in environment variables")
        return False
    
    client = get_anthropic_client(api_key)
    
    print("🔗 Testing new semantic linking approach...")
    print(f"📝 Input text: {test_text.strip()}")
    print(f"🧠 Memory entries: {len(mock_memory)}")
    
    # Test the new translate_and_link function
    try:
        start_time = datetime.now()
        linked_result = await translate_and_link(client, test_text, mock_memory)
        end_time = datetime.now()
        
        print(f"✅ Translation with semantic linking completed in {(end_time - start_time).total_seconds():.2f}s")
        print(f"📄 Result:\n{linked_result}")
        
        # Check if links were inserted
        link_count = linked_result.count('[') and linked_result.count('](')
        print(f"🔗 Links found: {link_count}")
        
        # Validate translation contains Russian characters
        has_russian = any(ord('а') <= ord(c) <= ord('я') or ord('А') <= ord(c) <= ord('Я') for c in linked_result)
        
        if has_russian and link_count > 0:
            print("✅ Semantic linking test PASSED!")
            return True
        else:
            print("❌ Test failed - missing Russian characters or links")
            return False
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🧪 Testing New Semantic Linking Approach")
    print("=" * 50)
    
    success = asyncio.run(test_semantic_linking())
    
    if success:
        print("\n🎉 Semantic linking test passed! New approach is working.")
    else:
        print("\n💥 Test failed. Check the errors above.")
        sys.exit(1) 