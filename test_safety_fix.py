#!/usr/bin/env python3
"""Test that safety filter credit card detection works correctly."""

import sys
sys.path.insert(0, 'src')

from safety_filters import apply_safety_filters

test_cases = [
    ("Where is my package? Order #12345", False, "Normal order inquiry"),
    ("I'm going to kill myself if this isn't resolved", True, "Crisis keyword"),
    ("My credit card number is 4532-1234-5678-9010", True, "Credit card with hyphens"),
    ("My CC is 4532 1234 5678 9010", True, "Credit card with spaces"),
    ("Card: 4532123456789010", True, "Credit card no separators"),
    ("You're a fucking idiot", True, "Severe abuse"),
    ("This service is pathetic!!!", False, "Frustration but not severe abuse"),
    ("Order number 12345678", False, "Short order number, not CC"),
]

print("=" * 80)
print("SAFETY FILTER TEST - Credit Card Detection Fix")
print("=" * 80)
print()

all_passed = True

for text, should_escalate, description in test_cases:
    result = apply_safety_filters(text)
    actual_escalate = result['should_escalate']
    
    status = "✓ PASS" if actual_escalate == should_escalate else "✗ FAIL"
    if actual_escalate != should_escalate:
        all_passed = False
    
    print(f"{status} | {description}")
    print(f"  Text: \"{text[:60]}...\"")
    print(f"  Expected escalate: {should_escalate}, Got: {actual_escalate}")
    if result['escalation_reasons']:
        print(f"  Reasons: {result['escalation_reasons']}")
    print()

print("=" * 80)
if all_passed:
    print("✓ ALL TESTS PASSED")
else:
    print("✗ SOME TESTS FAILED - Review above")
print("=" * 80)
