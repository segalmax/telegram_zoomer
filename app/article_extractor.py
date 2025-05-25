"""
Simple article extractor for news URLs using newspaper4k.
MVP approach: fast, reliable, basic error handling.
"""

import logging
from typing import Optional
from newspaper import Article

logger = logging.getLogger(__name__)


def extract_article(url: str) -> str:
    """
    Extract article text from a URL.
    
    Args:
        url: The URL to extract article content from
        
    Returns:
        str: The extracted article text, or empty string if extraction fails
    """
    if not url or not url.strip():
        logger.warning("Empty URL provided to extract_article")
        return ""
    
    try:
        # Determine language based on domain
        if 'ynet.co.il' in url:
            language = 'he'  # Hebrew for ynet.co.il
        elif 'ynetnews.com' in url:
            language = 'en'  # English for ynetnews.com
        else:
            language = None  # Auto-detect for other sites
            
        # Create and configure article
        article = Article(url, language=language)
        
        # Download and parse
        article.download()
        article.parse()
        
        # Validate extraction
        if not article.text or len(article.text.strip()) < 50:
            logger.warning(f"Article text too short or empty for URL: {url}")
            return ""
            
        logger.info(f"Successfully extracted article: {len(article.text)} chars from {url}")
        return article.text.strip()
        
    except Exception as e:
        # Log as warning instead of error since 404s and other failures are expected
        logger.warning(f"Failed to extract article from {url}: {str(e)}")
        return ""


def extract_article_with_metadata(url: str) -> dict:
    """
    Extract article with additional metadata (title, author, etc.).
    
    Args:
        url: The URL to extract article content from
        
    Returns:
        dict: Article data with text, title, author, publish_date, etc.
    """
    result = {
        'text': '',
        'title': '',
        'authors': [],
        'publish_date': None,
        'top_image': '',
        'url': url
    }
    
    if not url or not url.strip():
        logger.warning("Empty URL provided to extract_article_with_metadata")
        return result
    
    try:
        # Determine language based on domain
        if 'ynet.co.il' in url:
            language = 'he'  # Hebrew for ynet.co.il
        elif 'ynetnews.com' in url:
            language = 'en'  # English for ynetnews.com
        else:
            language = None  # Auto-detect for other sites
            
        # Create and configure article
        article = Article(url, language=language)
        
        # Download and parse
        article.download()
        article.parse()
        
        # Extract all available data
        result['text'] = article.text.strip() if article.text else ''
        result['title'] = article.title.strip() if article.title else ''
        result['authors'] = article.authors if article.authors else []
        result['publish_date'] = article.publish_date
        result['top_image'] = article.top_image if article.top_image else ''
        
        # Validate extraction
        if not result['text'] or len(result['text']) < 50:
            logger.warning(f"Article text too short or empty for URL: {url}")
            
        logger.info(f"Successfully extracted article with metadata: {len(result['text'])} chars from {url}")
        return result
        
    except Exception as e:
        # Log as warning instead of error since 404s and other failures are expected
        logger.warning(f"Failed to extract article with metadata from {url}: {str(e)}")
        return result 