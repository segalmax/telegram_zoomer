"""
Simple article extractor for news URLs using newspaper4k.
MVP approach: fast, reliable, basic error handling.
"""

import logging
from typing import Optional
from urllib.parse import urlparse
from newspaper import Article
from .config_loader import get_config_loader

logger = logging.getLogger(__name__)

# Initialize configuration loader
config = get_config_loader()


def _extract_domain(url: str) -> str:
    """Extract domain name from URL for configuration lookup."""
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower()
    except Exception:
        return url  # Fallback to original URL if parsing fails


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
        # Get article extraction configuration from database using domain
        domain = _extract_domain(url)
        extraction_config = config.get_article_extraction_config(domain)
            
        # Create and configure article
        article = Article(url, language=extraction_config['language_code'])
        
        # Download and parse
        article.download()
        article.parse()
        
        # Extract text
        article_text = article.text
        
        if not article_text or not article_text.strip():
            logger.warning(f"No text content extracted from {url}")
            return ""
        
        logger.info(f"Successfully extracted {len(article_text)} characters from {url}")
        return article_text.strip()
        
    except Exception as e:
        logger.warning(f"Failed to extract article from {url}: {e}")
        return ""


async def aextract_article(url: str) -> str:
    """
    Async version of extract_article for use in async contexts.
    
    Args:
        url: The URL to extract article content from
        
    Returns:
        str: The extracted article text, or empty string if extraction fails
    """
    if not url or not url.strip():
        logger.warning("Empty URL provided to aextract_article")
        return ""
    
    try:
        # Get article extraction configuration from database using domain
        domain = _extract_domain(url)
        extraction_config = await config.aget_article_extraction_config(domain)
            
        # Create and configure article
        article = Article(url, language=extraction_config['language_code'])
        
        # Download and parse
        article.download()
        article.parse()
        
        # Validate extraction
        if not article.text or len(article.text.strip()) < extraction_config['min_article_length']:
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
        # Get article extraction configuration from database using domain
        domain = _extract_domain(url)
        extraction_config = config.get_article_extraction_config(domain)
            
        # Create and configure article
        article = Article(url, language=extraction_config['language_code'])
        
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
        if not result['text'] or len(result['text']) < extraction_config['min_article_length']:
            logger.warning(f"Article text too short or empty for URL: {url}")
            
        logger.info(f"Successfully extracted article with metadata: {len(result['text'])} chars from {url}")
        return result
        
    except Exception as e:
        # Log as warning instead of error since 404s and other failures are expected
        logger.warning(f"Failed to extract article with metadata from {url}: {str(e)}")
        return result 