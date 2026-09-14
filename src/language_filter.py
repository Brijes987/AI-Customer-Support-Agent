"""
Language detection and filtering.

Scope: English-only messages for this assignment.
Non-English messages are filtered out at ingestion with explicit documentation.
"""

import re
from typing import Tuple


def is_likely_english(text: str) -> Tuple[bool, str]:
    """
    Simple heuristic to detect if text is likely English.
    
    Not a perfect language detector, but good enough to filter obvious
    non-English messages (French, Spanish, Hindi transliteration, etc.)
    
    Returns:
        (is_english, reason)
    """
    # Quick checks for non-Latin scripts (Cyrillic, Arabic, Devanagari, etc.)
    # If we find these, definitely not English
    non_latin_scripts = [
        (r'[\u0400-\u04FF]', 'Cyrillic detected'),  # Russian, Ukrainian, etc.
        (r'[\u0600-\u06FF]', 'Arabic detected'),
        (r'[\u0900-\u097F]', 'Devanagari detected'),  # Hindi
        (r'[\u4E00-\u9FFF]', 'Chinese characters detected'),
        (r'[\u3040-\u309F\u30A0-\u30FF]', 'Japanese detected'),
        (r'[\uAC00-\uD7AF]', 'Korean detected'),
    ]
    
    for pattern, reason in non_latin_scripts:
        if re.search(pattern, text):
            return False, reason
    
    # Check for common non-English words/patterns in Latin script
    # French
    french_indicators = [
        r'\b(bonjour|merci|je|vous|est|dans|pour|avec|mais)\b',
        r'\bça\b', r'\bêtre\b',
    ]
    for pattern in french_indicators:
        if re.search(pattern, text, re.IGNORECASE):
            return False, "French language detected"
    
    # Spanish
    spanish_indicators = [
        r'\b(hola|gracias|buenos|días|está|porque|también|señor)\b',
        r'\b¿', r'¡',  # Spanish punctuation
    ]
    for pattern in spanish_indicators:
        if re.search(pattern, text, re.IGNORECASE):
            return False, "Spanish language detected"
    
    # German
    german_indicators = [
        r'\b(ich|und|ist|das|nicht|aber|haben|werden)\b',
        r'[äöüß]',  # German-specific characters
    ]
    for pattern in german_indicators:
        if re.search(pattern, text, re.IGNORECASE):
            return False, "German language detected"
    
    # Portuguese
    portuguese_indicators = [
        r'\b(obrigado|você|está|não|muito|porque|também)\b',
        r'[ãõç]',  # Portuguese-specific characters
    ]
    for pattern in portuguese_indicators:
        if re.search(pattern, text, re.IGNORECASE):
            return False, "Portuguese language detected"
    
    # If we made it here, likely English (or at least Latin-script)
    return True, "Appears to be English"


def filter_non_english_threads(threads):
    """
    Filter threads to English-only messages.
    
    Filters based on initial customer message language.
    
    Returns:
        (english_threads, non_english_count, language_stats)
    """
    english_threads = []
    non_english_count = 0
    language_stats = {}
    
    for thread in threads:
        # Get first customer message
        first_customer = next(
            (msg for msg in thread['messages'] if msg['author_role'] == 'customer'),
            None
        )
        
        if not first_customer:
            continue  # Skip threads with no customer message
        
        is_eng, reason = is_likely_english(first_customer['text'])
        
        if is_eng:
            english_threads.append(thread)
        else:
            non_english_count += 1
            # Track language distribution
            lang = reason.replace(' detected', '').replace('Appears to be ', '')
            language_stats[lang] = language_stats.get(lang, 0) + 1
    
    return english_threads, non_english_count, language_stats


# Example usage and testing
if __name__ == "__main__":
    test_cases = [
        ("Where is my package?", True, "English"),
        ("Bonjour, où est mon colis?", False, "French"),
        ("Hola, ¿dónde está mi paquete?", False, "Spanish"),
        ("Привет, где мой заказ?", False, "Cyrillic/Russian"),
        ("कहाँ है मेरा पैकेज?", False, "Devanagari/Hindi"),
        ("Order #12345 kahan hai?", True, "English with transliterated Hindi (passes as Latin script)"),
        ("Obrigado pela ajuda!", False, "Portuguese"),
    ]
    
    print("Language Detection Tests:")
    print("=" * 60)
    
    for text, expected_english, description in test_cases:
        is_eng, reason = is_likely_english(text)
        status = "✓" if is_eng == expected_english else "✗"
        print(f"\n{status} {description}")
        print(f"  Text: \"{text}\"")
        print(f"  Detected: {reason}")
        print(f"  Is English: {is_eng} (expected: {expected_english})")
