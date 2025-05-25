#!/usr/bin/env python3
"""
Quick test of the article extractor module
"""

import sys
import os

# Add app directory to path (go up one level from tests/ to project root, then into app/)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from article_extractor import extract_article, extract_article_with_metadata

def test_article_extraction():
    """Test article extraction functionality"""
    # Test URL from our previous successful test
    test_url = "https://www.ynet.co.il/digital/technews/article/sjbqaynwyl"
    
    print("=== Testing extract_article() ===")
    text = extract_article(test_url)
    print(f"Extracted text length: {len(text)}")
    print(f"Text preview: {text[:200]}...")
    
    # Assert that we got meaningful content
    assert text, "Article text should not be empty"
    assert len(text) > 100, "Article text should be substantial"
    
    print("\n=== Testing extract_article_with_metadata() ===")
    metadata = extract_article_with_metadata(test_url)
    print(f"Title: {metadata['title']}")
    print(f"Authors: {metadata['authors']}")
    print(f"Publish date: {metadata['publish_date']}")
    print(f"Text length: {len(metadata['text'])}")
    print(f"Top image: {metadata['top_image']}")
    
    # Assert metadata is properly extracted
    assert metadata['title'], "Title should not be empty"
    assert metadata['text'] == text, "Text should match between functions"
    assert len(metadata['authors']) > 0, "Should have at least one author"

def test_error_handling():
    """Test error handling for invalid URLs"""
    print("\n=== Testing error handling ===")
    
    # Test with invalid URL
    empty_result = extract_article("https://invalid-url-that-does-not-exist.com")
    print(f"Invalid URL result: '{empty_result}' (should be empty)")
    assert empty_result == "", "Invalid URL should return empty string"
    
    # Test with empty URL
    empty_result2 = extract_article("")
    print(f"Empty URL result: '{empty_result2}' (should be empty)")
    assert empty_result2 == "", "Empty URL should return empty string"

if __name__ == "__main__":
    test_article_extraction()
    test_error_handling()
    print("\n✅ All tests passed!") 