#!/usr/bin/env python3
"""
Test script to verify Claude translation integration
"""

import os
import asyncio
import sys
from pathlib import Path
import pytest

# Add the project root to Python path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from app.translator import get_anthropic_client, translate_text

# Load environment variables
load_dotenv()

@pytest.mark.asyncio
async def test_claude_translation():
    """Test Claude translation functionality"""
    
    # Check for API key
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("❌ ANTHROPIC_API_KEY not found in environment")
        print("Please add ANTHROPIC_API_KEY to your .env file")
        return False
    
    print("✅ ANTHROPIC_API_KEY found")
    
    # Initialize client
    try:
        client = get_anthropic_client(api_key)
        print("✅ Anthropic client initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize Anthropic client: {e}")
        return False
    
    # Test translation
    test_text = "Breaking: Scientists discover new method to reduce carbon emissions by 40% using innovative technology."
    
    print(f"\n🔄 Testing translation...")
    print(f"Original text: {test_text}")
    
    try:
        # Test RIGHT style translation
        print("\n🔄 Testing RIGHT style translation...")
        translated_right = await translate_text(client, test_text, 'right')
        print(f"✅ RIGHT translation: {translated_right[:100]}...")
        
        # Test LEFT style translation  
        print("\n🔄 Testing LEFT style translation...")
        translated_left = await translate_text(client, test_text, 'left')
        print(f"✅ LEFT translation: {translated_left[:100]}...")
        
        # Validate translations contain Russian characters
        has_russian_right = any(ord('а') <= ord(c) <= ord('я') or ord('А') <= ord(c) <= ord('Я') for c in translated_right)
        has_russian_left = any(ord('а') <= ord(c) <= ord('я') or ord('А') <= ord(c) <= ord('Я') for c in translated_left)
        
        if has_russian_right and has_russian_left:
            print("✅ Both translations contain Russian characters")
            print("✅ Claude translation integration test PASSED!")
            return True
        else:
            print("❌ Translations missing Russian characters")
            return False
            
    except Exception as e:
        print(f"❌ Translation failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing Claude Translation Integration")
    print("=" * 50)
    
    success = asyncio.run(test_claude_translation())
    
    if success:
        print("\n🎉 All tests passed! Claude translation is ready.")
    else:
        print("\n💥 Tests failed. Check the errors above.")
        sys.exit(1) 