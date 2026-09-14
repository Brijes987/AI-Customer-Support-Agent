"""
Safety filters for customer messages.

Pre-classification checks that flag messages for mandatory human escalation
regardless of predicted intent or confidence.
"""

import re
from typing import Dict, List, Tuple


def check_crisis_keywords(text: str) -> Tuple[bool, str]:
    """
    Flag messages containing self-harm, crisis, or sensitive content.
    
    Returns:
        (should_escalate, reason)
    """
    text_lower = text.lower()
    
    # Self-harm and crisis keywords
    crisis_keywords = [
        'kill myself', 'suicide', 'suicidal', 'end my life', 'want to die',
        'harm myself', 'self harm', 'cut myself', 'overdose',
        'no reason to live', 'better off dead',
    ]
    
    for keyword in crisis_keywords:
        if keyword in text_lower:
            return True, f"Crisis keyword detected: '{keyword}'"
    
    # Threatening language (toward others)
    threat_keywords = [
        'going to kill', 'will kill', 'hurt you', 'find you',
        'stalk', 'stalking', 'harass', 'threaten',
    ]
    
    for keyword in threat_keywords:
        if keyword in text_lower:
            return True, f"Threat language detected: '{keyword}'"
    
    return False, ""


def check_personal_information_exposure(text: str) -> Tuple[bool, str]:
    """
    Flag messages that may contain exposed sensitive personal information.
    
    Not a perfect PII detector, but catches obvious cases that should be escalated
    for human review to avoid exposing data.
    
    Returns:
        (should_escalate, reason)
    """
    # Social Security Number patterns (XXX-XX-XXXX or similar)
    ssn_pattern = r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b'
    if re.search(ssn_pattern, text):
        return True, "Possible SSN detected"
    
    # Credit card patterns (13-19 digits, possibly with hyphens or spaces)
    # Matches formats like: 4532123456789010, 4532-1234-5678-9010, 4532 1234 5678 9010
    cc_pattern = r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{3,4}\b'
    if re.search(cc_pattern, text):
        # Extract just digits to check length
        matches = re.findall(cc_pattern, text)
        for match in matches:
            digits_only = re.sub(r'[-\s]', '', match)
            if 13 <= len(digits_only) <= 19:  # Credit cards are 13-19 digits
                return True, "Possible credit card number detected"
    
    return False, ""


def check_abusive_language(text: str) -> Tuple[bool, str]:
    """
    Flag messages with severe abusive language directed at agents.
    
    Mild frustration is okay, but severe abuse should escalate.
    
    Returns:
        (should_escalate, reason)
    """
    text_lower = text.lower()
    
    # Severe slurs or targeted abuse (this is a minimal list - expand as needed)
    severe_abuse = [
        'fuck you', 'fucking idiot', 'stupid bitch',
        'go to hell', 'i hope you',  # Often followed by threats
    ]
    
    for phrase in severe_abuse:
        if phrase in text_lower:
            return True, f"Severe abusive language detected"
    
    return False, ""


def apply_safety_filters(text: str) -> Dict[str, any]:
    """
    Apply all safety filters to a message.
    
    Returns dict with:
        - should_escalate: bool
        - escalation_reasons: List[str]
        - filter_results: Dict of individual filter results
    """
    results = {
        'should_escalate': False,
        'escalation_reasons': [],
        'filter_results': {},
    }
    
    # Crisis check
    crisis_flag, crisis_reason = check_crisis_keywords(text)
    results['filter_results']['crisis'] = {'flagged': crisis_flag, 'reason': crisis_reason}
    if crisis_flag:
        results['should_escalate'] = True
        results['escalation_reasons'].append(crisis_reason)
    
    # PII exposure check
    pii_flag, pii_reason = check_personal_information_exposure(text)
    results['filter_results']['pii'] = {'flagged': pii_flag, 'reason': pii_reason}
    if pii_flag:
        results['should_escalate'] = True
        results['escalation_reasons'].append(pii_reason)
    
    # Abusive language check
    abuse_flag, abuse_reason = check_abusive_language(text)
    results['filter_results']['abuse'] = {'flagged': abuse_flag, 'reason': abuse_reason}
    if abuse_flag:
        results['should_escalate'] = True
        results['escalation_reasons'].append(abuse_reason)
    
    return results


# Example usage
if __name__ == "__main__":
    test_cases = [
        "Where is my package? Order #12345",
        "I'm going to kill myself if this isn't resolved",
        "My credit card number is 4532-1234-5678-9010",
        "You're a fucking idiot",
        "This service is pathetic!!!",  # Frustration but not severe abuse
    ]
    
    for text in test_cases:
        result = apply_safety_filters(text)
        print(f"\nText: \"{text[:50]}...\"")
        print(f"  Escalate: {result['should_escalate']}")
        if result['escalation_reasons']:
            print(f"  Reasons: {result['escalation_reasons']}")
