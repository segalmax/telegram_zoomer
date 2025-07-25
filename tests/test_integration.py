#!/usr/bin/env python3
"""
Test integration between article extraction and translation
"""

# Load environment variables FIRST before any imports that need them
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=project_root / 'app_settings.env', override=True)
load_dotenv(dotenv_path=project_root / '.env', override=False)

# Now safe to import modules that need environment variables
import sys
import os
import asyncio

from app.autogen_translation import get_anthropic_client

# Add project root directory to path so we can import the app package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.article_extractor import extract_article
from app.autogen_translation import translate_and_link

import pytest

@pytest.mark.asyncio
async def test_article_extraction_integration():
    """Test the integration between article extraction and translation"""
    
    # Test URL from ynet.co.il
    test_url = "https://www.ynet.co.il/digital/technews/article/sjbqaynwyl"
    
    print("=== Testing Article Extraction ===")
    article_text = extract_article(test_url)
    print(f"Extracted article length: {len(article_text)} characters")
    print(f"Article preview: {article_text[:200]}...")
    
    # Assert article extraction works
    assert article_text, "Article extraction should return content"
    assert len(article_text) > 100, "Article should have substantial content"
    
    print("\n=== Testing Translation Integration ===")
    
    # Simulate the message format that would come from Telegram
    original_message = "חדשות טכנולוגיה: בינה מלאכותית בחינוך"
    
    # Build translation context like the bot does
    translation_context = original_message
    translation_context += f"\n\nArticle content from {test_url}:\n{article_text}"
    
    print(f"Translation context length: {len(translation_context)} characters")
    print(f"Context preview: {translation_context[:300]}...")
    
    # Assert context is properly built
    assert len(translation_context) > len(original_message), "Context should be enhanced with article content"
    assert test_url in translation_context, "Context should include the URL"
    assert article_text in translation_context, "Context should include article text"
    
    # Test translation with semantic linking (requires Anthropic API key)
    api_key = os.getenv('ANTHROPIC_API_KEY')
    assert api_key, "ANTHROPIC_API_KEY environment variable is required for semantic linking test"
    
    # Insert test memories with embeddings for linking test
    from app.vector_store import save_pair, _embed
    import uuid
    
    test_memories = []
    test_ids = []
    try:
        # Create 3 test memory entries that should be linked (AI/education themed to match content)
        test_data = [
            ("Artificial intelligence transforms education systems", "Искусственный интеллект преобразует образовательные системы", "https://t.me/test/100"),
            ("Students use AI tutors for personalized learning", "Студенты используют ИИ-репетиторов для персонализированного обучения", "https://t.me/test/101"),  
            ("Teachers adapt to digital technology in classrooms", "Учителя адаптируются к цифровым технологиям в классах", "https://t.me/test/102")
        ]
        
        for src, tgt, url in test_data:
            test_id = f"test-{uuid.uuid4()}"
            test_ids.append(test_id)
            save_pair(src, tgt, test_id, message_url=url)
            
            # Build memory entry like bot does
            embedding = _embed(src)
            test_memories.append({
                'id': test_id,
                'translation_text': tgt,
                'message_url': url,
                'similarity': 0.9  # High similarity to ensure linking
            })
        
        client = get_anthropic_client(api_key)
        # Test with memories that should trigger semantic links
        translated, conversation_log = await translate_and_link(translation_context, test_memories)
        
        print(f"\n=== Translation with Linking Result ===")
        print(f"Translated text length: {len(translated)} characters")
        print(f"Translation: {translated}")
        
        # Assert translation works
        assert translated, "Translation should return content"
        assert len(translated) > 100, "Translation should be substantial"
        
        # CRITICAL TEST: Check for semantic links to previous messages
        import re
        links = re.findall(r'\[([^\]]+)\]\((https://t\.me/[^\)]+)\)', translated)
        assert len(links) >= 2, f"Expected at least 2 semantic links to previous messages, found {len(links)}: {links}"
        
        print(f"✅ Found {len(links)} semantic links: {links}")
        print("\n✅ Integration with semantic linking test successful!")
        
    finally:
        # Cleanup test data
        from app.vector_store import _sb
        if _sb and test_ids:
            for test_id in test_ids:
                try:
                    _sb.table("article_chunks").delete().eq("id", test_id).execute()
                except Exception as e:
                    print(f"Cleanup warning: {e}")

if __name__ == "__main__":
    asyncio.run(test_article_extraction_integration())
    print("\n🎉 Integration working correctly!") 