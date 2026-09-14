#!/usr/bin/env python3
"""
Test specific problem cases to verify classification logic is correct.
"""

import sys
sys.path.insert(0, 'scripts')

from collections import namedtuple

# Import the classification function
exec(open('scripts/06_refine_taxonomy.py', encoding='utf-8').read(), globals())

# Test cases from user's review
test_cases = [
    {
        'text': "Returned from a few days away to find my (very wet) parcel just chucked over my front wall",
        'expected': 'order_issue',  # Product damage (wet, chucked)
        'not': 'refund_return_request',  # No explicit refund ask
        'description': 'Wet parcel - product damage, not refund',
    },
    {
        'text': "I am a Prime member but I am not definitely getting prime service from you",
        'expected': None,  # Should NOT be order_issue
        'not': 'order_issue',  # Prime service complaint
        'description': 'Prime service complaint - NOT product issue',
    },
    {
        'text': "Still unresolved - no clue where the shipment is",
        'expected': 'delivery_status_inquiry',  # Delivery follow-up
        'not': 'general_inquiry',  # Should route to delivery
        'description': 'Delivery follow-up - should be delivery_status',
    },
    {
        'text': "NOTHING YET. WOW",
        'expected': 'complaint_no_action',  # Pure venting
        'not': 'general_inquiry',
        'description': 'Pure venting - no actionable request',
    },
]

print("=" * 80)
print("CLASSIFICATION LOGIC TEST - Specific Problem Cases")
print("=" * 80)
print()

all_passed = True

for i, case in enumerate(test_cases, 1):
    text = case['text']
    expected = case['expected']
    not_expected = case['not']
    description = case['description']
    
    # Classify
    intent, reason = classify_message_refined(text)
    
    # Check expectations
    passed = True
    if expected and intent != expected:
        passed = False
        all_passed = False
        status = f"✗ FAIL - Expected '{expected}', got '{intent}'"
    elif not_expected and intent == not_expected:
        passed = False
        all_passed = False
        status = f"✗ FAIL - Got '{intent}' but this should NOT be '{not_expected}'"
    else:
        status = f"✓ PASS - Classified as '{intent}'"
    
    print(f"Test {i}: {description}")
    print(f"  Text: \"{text[:70]}...\"")
    print(f"  {status}")
    print(f"  Reason: {reason}")
    print()

print("=" * 80)
if all_passed:
    print("✓ ALL TESTS PASSED - Classification logic is correct")
else:
    print("✗ SOME TESTS FAILED - Classification logic needs more fixes")
print("=" * 80)
