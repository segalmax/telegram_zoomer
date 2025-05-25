#!/usr/bin/env python3
"""
Test integration between article extraction and translation
"""

import sys
import os
import asyncio

# Add app directory to path (go up one level from tests/ to project root, then into app/)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from article_extractor import extract_article
from translator import get_openai_client, translate_text

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
    
    # Test translation (requires OpenAI API key)
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("⚠️  No OPENAI_API_KEY found, skipping translation test")
        print("✅ Integration structure looks correct!")
        pytest.skip("No OpenAI API key available for translation test")
    
    client = get_openai_client(api_key)
    translated = await translate_text(client, translation_context, 'left')
    
    print(f"\n=== Translation Result ===")
    print(f"Translated text length: {len(translated)} characters")
    print(f"Translation: {translated}")
    
    # Assert translation works
    assert translated, "Translation should return content"
    assert len(translated) > 100, "Translation should be substantial"
    
    print("\n✅ Integration test successful!")

if __name__ == "__main__":
    asyncio.run(test_article_extraction_integration())
    print("\n🎉 Integration working correctly!") 