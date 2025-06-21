"""Utility to inject navigation links to previous Telegram messages.

This module is a lightweight MVP implementation that:
1. Extracts up to *n* key phrases from the translated text.
2. Matches those phrases against the *translation_text* of the existing TM recall
   results (already available in *bot.py*).
3. Replaces the phrase with a Markdown hyperlink that leads back to the original
   Telegram message (``https://t.me/<channel>/<msg_id>``).

The goal is to keep the algorithm simple and dependency-free while still being
useful. It purposely avoids heavyweight NLP libraries so it can run in
resource-constrained Heroku dynos.
"""
from __future__ import annotations

import re
import logging
from difflib import SequenceMatcher
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Phrase extraction
# ---------------------------------------------------------------------------

# Improved pattern that extracts diverse phrases throughout the text
_PHRASE_PATTERN = re.compile(
    r"(?<!\w)(?:"
    # Temporal references (Russian/English)
    r"вчера|сегодня|накануне|ранее|прошл[а-я]+|эт[а-я]+|последн[а-я]+|\d{4}\s*год|"
    r"yesterday|today|recently|previously|last\s+\w+|this\s+\w+|"
    # Named entities/proper nouns (starts with capital, reasonable length)
    r"[A-ZА-Я][a-zA-Zа-я0-9\s\-]{3,30}(?=[\s\.\,\!\?\:\;]|$)|"
    # Key phrases with numbers/dates
    r"\d+[а-я\-]*\s*[а-я]+|\w+\s*\d{2,4}|"
    # Important words in context 
    r"(?:Трамп|Байден|Путин|Зеленский|Израиль|Иран|США|Украина|Россия)[a-zA-Zа-я0-9\s\-]{0,25}|"
    # Military/political terms and concepts (more flexible)
    r"(?:бомб|ракет|невидим|стратег|ядерн|завод|персид|американ|израиль)[а-я]*[\s\-]*[а-я]*|"
    # Action phrases and verbs with context
    r"[а-я]+\s+(?:бомбы|заводы|ракеты|невидимки|самолёты)|"
    # Descriptive phrases (adjective + noun combinations)  
    r"(?:сверхзащищённый|стратегический|ядерный|американский|израильский|иранский)\s+[а-я]+|"
    # Technical terms and specifications
    r"B-\d+|GBU-\d+|[А-Я]{2,4}-\d+|\d+[,\.]\d*\s*тонн|"
    # Geographic and facility references
    r"(?:Фордо|Нетанц|Исфахан|Арак|Гуам|Уайтмен|Миссури)\w*"
    r")",
    flags=re.IGNORECASE,
)


def _clean_phrase(phrase: str) -> str:
    """Clean extracted phrase from markdown and formatting."""
    # Remove markdown formatting
    phrase = re.sub(r'\*\*([^*]+)\*\*', r'\1', phrase)  # **bold**
    phrase = re.sub(r'\*([^*]+)\*', r'\1', phrase)      # *italic*
    phrase = re.sub(r'`([^`]+)`', r'\1', phrase)        # `code`
    # Remove newlines and normalize spaces
    phrase = re.sub(r'\s+', ' ', phrase.replace('\n', ' '))
    # Remove trailing punctuation and markdown
    phrase = phrase.strip(' .,!?:;*#-')
    return phrase


def extract_key_phrases(text: str, max_phrases: int = 10) -> List[str]:
    """Return up to *max_phrases* potentially link-worthy phrases from *text*.

    Enhanced approach with better distribution:
    • Extracts phrases from different sections of text (title, body paragraphs)
    • Uses regex patterns to capture specific entities and technical terms
    • Extracts multi-word phrases (2-4 words) that could be meaningful
    • Prioritizes phrases with military/political/geographic significance
    • Ensures phrases are distributed throughout the text, not just the beginning
    • More generous extraction to allow up to 10 links per post
    """
    if not text:
        return []

    seen: set[str] = set()
    phrases: List[str] = []
    
    # Split text into sections for better distribution
    lines = text.split('\n')
    title_section = lines[0] if lines else ""
    body_sections = []
    
    # Group non-empty lines into paragraphs
    current_paragraph = []
    for line in lines[1:]:
        if line.strip():
            current_paragraph.append(line)
        elif current_paragraph:
            body_sections.append('\n'.join(current_paragraph))
            current_paragraph = []
    if current_paragraph:
        body_sections.append('\n'.join(current_paragraph))
    
    # Extract phrases from each section - more generous allocation
    sections = [("title", title_section)] + [(f"para_{i}", para) for i, para in enumerate(body_sections)]
    
    # Allow more phrases per section, but still try to distribute
    if len(sections) <= 2:
        phrases_per_section = max_phrases  # If few sections, extract generously
    else:
        phrases_per_section = max(2, max_phrases // len(sections) + 1)  # At least 2 per section
    
    for section_name, section_text in sections:
        if len(phrases) >= max_phrases:
            break
            
        if not section_text.strip():
            continue
            
        logger.debug(f"🔗 Extracting from {section_name}: {section_text[:50]}...")
        section_phrases = []
        
        # Strategy 1: Pattern-based extraction
        for m in _PHRASE_PATTERN.finditer(section_text):
            raw_phrase = m.group(0).strip()
            phrase = _clean_phrase(raw_phrase)
            
            if len(phrase) >= 4:
                low = phrase.lower()
                if low not in seen:
                    seen.add(low)
                    section_phrases.append(phrase)
                    if len(section_phrases) >= phrases_per_section:
                        break
        
        # Strategy 2: Multi-word phrase extraction - more aggressive
        if len(section_phrases) < phrases_per_section:
            sentences = re.split(r'[.!?]+', section_text)
            
            for sentence in sentences:
                if len(section_phrases) >= phrases_per_section * 2:  # Allow double quota for multi-word
                    break
                    
                clean_sentence = _clean_phrase(sentence).strip()
                words = clean_sentence.split()
                
                # Extract 2-4 word combinations
                for i in range(len(words)):
                    if len(section_phrases) >= phrases_per_section * 2:
                        break
                        
                    for phrase_len in [4, 3, 2]:  # Try longer phrases first
                        if i + phrase_len <= len(words):
                            candidate = ' '.join(words[i:i + phrase_len])
                            
                            # More lenient filtering - allow more phrases through
                            if len(candidate) < 6 or len(candidate) > 60:
                                continue
                                
                            # Skip obvious stop word combinations but be more permissive
                            stop_heavy = sum(1 for stop in ['и', 'в', 'на', 'с', 'для', 'от', 'по', 'что', 'как', 'это', 'все', 'так', 'уже', 'но', 'или', 'если'] if stop in candidate.lower().split())
                            if stop_heavy >= len(candidate.split()) // 2:  # More than half stop words
                                continue
                                
                            low = candidate.lower()
                            if low not in seen:
                                seen.add(low)
                                section_phrases.append(candidate)
                                break
        
        # Add section phrases to main list
        phrases.extend(section_phrases)
        logger.debug(f"🔗 {section_name}: found {len(section_phrases)} phrases")
    
    # Take all extracted phrases up to max_phrases
    phrases = phrases[:max_phrases]
    
    logger.info(f"🔗 Extracted {len(phrases)} key phrases from {len(text)} chars across {len(sections)} sections: {phrases}")
    return phrases

# ---------------------------------------------------------------------------
# Matching phrases to TM memory
# ---------------------------------------------------------------------------

def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def match_phrases_to_memory(
    phrases: List[str],
    memory: List[Dict[str, Any]],
    similarity_threshold: float = 0.5,  # Lower threshold for better matching
) -> Dict[str, Dict[str, Any]]:
    """For each *phrase* return the best matching memory entry (if any).

    The memory list comes from ``recall_tm`` and contains ``translation_text``
    plus optional message metadata (``message_url`` etc.).
    
    Each memory item/URL will be used only once to avoid redundant links.
    """
    matches: Dict[str, Dict[str, Any]] = {}
    used_urls: set[str] = set()  # Track URLs already used for linking

    for phrase in phrases:
        best: tuple[float, Dict[str, Any] | None] = (0.0, None)
        phrase_lower = phrase.lower()
        phrase_words = set(phrase_lower.split())
        
        for item in memory:
            text = item.get("translation_text") or ""
            text_lower = text.lower()
            url = item.get("message_url")
            
            # Skip if this URL was already used for another phrase
            if url and url in used_urls:
                continue
            
            # Try multiple matching strategies
            sim = 0.0
            
            # Strategy 1: Direct substring match (highest score)
            if phrase_lower in text_lower:
                sim = max(sim, 0.9)
            
            # Strategy 2: Reverse substring match (phrase contains text words)
            text_words = set(text_lower.split())
            if phrase_words & text_words:  # Any word overlap
                overlap_ratio = len(phrase_words & text_words) / len(phrase_words)
                sim = max(sim, overlap_ratio * 0.8)
            
            # Strategy 3: Fuzzy string similarity
            fuzzy_sim = _similar(phrase, text)
            if fuzzy_sim > 0.3:  # Only consider if reasonable similarity
                sim = max(sim, fuzzy_sim)
            
            # Strategy 4: Check if any significant word from phrase appears in text
            significant_words = [w for w in phrase_words if len(w) > 3]
            for word in significant_words:
                if word in text_lower:
                    sim = max(sim, 0.6)
                    break
                    
            if sim > best[0]:
                best = (sim, item)
        
        if best[1] and best[0] >= similarity_threshold:
            url = best[1].get("message_url")
            if url and url not in used_urls:  # Double-check URL isn't used
                matches[phrase] = best[1]  # type: ignore[arg-type]
                used_urls.add(url)  # Mark this URL as used
                logger.info(f"🔗 Matched phrase '{phrase}' with similarity {best[0]:.3f} to {url}")

    logger.info(
        "🔗 Found %d phrase->memory matches (using %d unique URLs): %s",
        len(matches),
        len(used_urls),
        {p: f"{m.get('message_url', 'no-url')} (sim={_similar(p, m.get('translation_text', '')):.2f})" 
         for p, m in matches.items()},
    )
    return matches

# ---------------------------------------------------------------------------
# Link insertion
# ---------------------------------------------------------------------------

def insert_navigation_links(text: str, matches: Dict[str, Dict[str, Any]]) -> str:
    """Return *text* with matched phrases converted to Markdown links."""
    if not matches:
        return text

    # Sort phrases by length DESC to avoid nested replacement issues
    for phrase in sorted(matches.keys(), key=len, reverse=True):
        target = matches[phrase]
        url = target.get("message_url")
        if not url:
            continue  # cannot create link
        escaped = re.escape(phrase)
        # Replace only the first occurrence to avoid spammy links
        text, n = re.subn(
            escaped,
            f"[{phrase}]({url})",
            text,
            count=1,
            flags=re.IGNORECASE,
        )
        logger.info(f"🔗 Replaced {phrase!r} with link ({n} substitutions)")

    return text

# Convenience wrapper --------------------------------------------------------

def add_navigation_links(
    translated_text: str,
    memory: List[Dict[str, Any]],
    max_phrases: int = 10,  # Increased to allow up to 10 links
) -> str:
    """High-level helper used by the bot pipeline."""
    logger.info(f"🔗 Starting navigation link generation for text: {translated_text[:100]}...")
    logger.info(f"🔗 Memory available: {len(memory)} items")
    
    # Debug: show sample memory content
    for i, item in enumerate(memory[:3]):  # Show first 3 items
        text_preview = (item.get("translation_text") or "")[:60]
        url = item.get("message_url", "no-url")
        logger.info(f"🔗 Memory[{i}]: '{text_preview}...' -> {url}")
    
    phrases = extract_key_phrases(translated_text, max_phrases=max_phrases)
    matches = match_phrases_to_memory(phrases, memory)
    result = insert_navigation_links(translated_text, matches)
    
    if result != translated_text:
        logger.info(f"🔗 Navigation links added successfully")
    else:
        logger.info(f"🔗 No navigation links were added")
    
    return result 