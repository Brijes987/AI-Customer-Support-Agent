#!/usr/bin/env python3
"""
Stage 6: Refine taxonomy with quality checks.

Fixes:
1. Deduplicate examples across intents
2. Validate examples match intent descriptions
3. Add missing categories (account access)
4. Split GENERAL_INQUIRY from COMPLAINT_NO_ACTION
5. Explicit disambiguation rules

Does NOT handle language filtering or safety checks (separate pipeline stages).
"""

import argparse
import json
import re
from pathlib import Path
from collections import defaultdict


def load_sampled_threads(sample_file):
    """Load sampled threads from JSONL."""
    with open(sample_file, 'r', encoding='utf-8') as f:
        threads = [json.loads(line) for line in f]
    return threads


def extract_customer_messages(threads):
    """Extract first customer message from each thread."""
    messages = []
    for thread in threads:
        first_customer = next(
            (msg for msg in thread['messages'] if msg['author_role'] == 'customer'),
            None
        )
        if first_customer:
            messages.append({
                'text': first_customer['text'],
                'thread': thread,
            })
    return messages


def classify_message_refined(text):
    """
    Refined intent classification with explicit disambiguation rules.
    
    CRITICAL: Order matters! More specific checks must come before general ones.
    
    Returns (intent, confidence_reason).
    """
    text_lower = text.lower()
    
    # PRIORITY 1: Delivery status (including follow-ups with "where"/"when")
    # Check this FIRST before general_inquiry can claim "where"/"when" questions
    delivery_keywords = [
        'where is', 'when will', 'when is', 'tracking', 'delivered', 'arrive', 'arrived', 
        'shipping', 'status', 'shipment', 'package', 'parcel',
        # Follow-up phrases
        'not here', 'still waiting', 'hasnt arrived', "hasn't arrived", 'still unresolved',
        'no clue where', 'where is it', 'when will it arrive'
    ]
    
    has_delivery_question = any(kw in text_lower for kw in delivery_keywords)
    
    # Check for product problems (might override delivery if both present)
    order_problem_keywords = ['wrong item', 'damaged', 'broken', 'missing', 'not what', 'different', 'defective', 'incorrect', 'faulty', 'wet parcel', 'chucked']
    has_order_problem = any(kw in text_lower for kw in order_problem_keywords)
    
    # PRIORITY 2: Product problems (override delivery timing questions)
    if has_order_problem:
        return 'order_issue', 'Product problem mentioned'
    
    # PRIORITY 3: Delivery questions (including "where"/"when" follow-ups)
    if has_delivery_question:
        return 'delivery_status_inquiry', 'Asking about delivery status/timing (includes follow-ups)'
    
    # PRIORITY 4: Explicit refund/return requests
    refund_keywords = ['refund', 'money back', 'return', 'send back', 'cancel order', 'give me my money', 'want my money']
    if any(kw in text_lower for kw in refund_keywords):
        return 'refund_return_request', 'Explicit refund/return request'
    
    # PRIORITY 5: Payment/billing issues
    payment_keywords = ['charge', 'charged', 'payment', 'billing', 'unauthorized', 'credit card', 'debit', 'overcharge', 'double charge']
    if any(kw in text_lower for kw in payment_keywords):
        return 'payment_billing_issue', 'Payment/billing concern'
    
    # PRIORITY 6: Account access
    account_keywords = ['login', 'log in', 'password', 'sign in', 'account lock', 'cant access', "can't access", 'locked out', 'reset password']
    if any(kw in text_lower for kw in account_keywords):
        return 'account_access_issue', 'Account access problem'
    
    # PRIORITY 7: Prime membership (NOT service complaints)
    prime_keywords = ['prime membership', 'prime subscription', 'prime trial', 'prime benefits', 'cancel prime', 'prime account']
    # Explicitly exclude Prime service complaints
    prime_service_complaint = ('not getting prime service' in text_lower or 
                              'not definitely getting prime service' in text_lower or
                              ('prime member' in text_lower and 'not' in text_lower and 'service' in text_lower))
    
    if any(kw in text_lower for kw in prime_keywords) and not prime_service_complaint:
        return 'prime_membership_inquiry', 'Prime subscription/membership question'
    
    # PRIORITY 8: Pure venting (no specific ask)
    venting_phrases = ['pathetic', 'terrible service', 'worst', 'disgusting', 'useless', 'ridiculous', 'joke', 'appalling', 'nothing yet', 'wow']
    has_venting = any(phrase in text_lower for phrase in venting_phrases)
    
    # Check for actionable content
    explicit_questions = ['how do i', 'can you', 'will you', 'could you', 'what is', 'why is']  # NOT "where"/"when" alone
    action_requests = ['need to', 'want to', 'help me', 'please', 'can i', 'send me', 'give me']
    has_actionable = any(q in text_lower for q in explicit_questions + action_requests)
    
    # Pure venting: venting phrases + no actionable content
    if has_venting and not has_actionable and len(text) < 150:
        return 'complaint_no_action', 'Pure venting, no specific request'
    
    # PRIORITY 9: General inquiry (STRICT - only if has clear question/request)
    # At this point, "where"/"when" about delivery are already caught
    question_markers = ['how do i', 'how can i', 'how to', 'can you', 'could you', 'would you',
                       'will you', 'what is', 'what are', 'why is', 'why did', 'why cant',
                       'when can', 'is it possible', '?']
    action_requests = ['please help', 'help me', 'need to', 'want to', 'can i', 'could i',
                      'send me', 'give me', 'let me know']
    
    has_question = any(marker in text_lower for marker in question_markers)
    has_request = any(req in text_lower for req in action_requests)
    
    if has_question or has_request:
        return 'general_inquiry', 'General question or request'
    
    # PRIORITY 10: Everything else without clear structure = complaint/venting
    # This catches messages that don't fit anywhere else
    return 'complaint_no_action', 'No clear question or request (fallback)'


def validate_example_matches_intent(text, intent_data):
    """
    Validate that an example actually matches its intent's description.
    
    CRITICAL: This validates AFTER classification. If the example doesn't match,
    it means the classification logic is wrong.
    
    Returns (is_valid, reason).
    """
    text_lower = text.lower()
    intent = intent_data['intent']
    
    # Intent-specific STRICT validation
    if intent == 'refund_return_request':
        # MUST explicitly mention refund/return
        refund_words = ['refund', 'return', 'money back', 'send back', 'cancel order']
        if not any(word in text_lower for word in refund_words):
            return False, f"No explicit refund/return keyword found. Text: '{text[:80]}...'"
    
    elif intent == 'order_issue':
        # MUST mention product problem, NOT Prime service complaints
        product_problem_words = ['wrong', 'damaged', 'broken', 'missing', 'defective', 'faulty', 'incorrect', 'wet parcel', 'chucked']
        
        # Check for Prime service complaints
        if 'prime' in text_lower and 'service' in text_lower and 'not' in text_lower:
            return False, f"Prime service complaint, not product issue. Text: '{text[:80]}...'"
        
        if not any(word in text_lower for word in product_problem_words):
            return False, f"No product problem keyword found. Text: '{text[:80]}...'"
    
    elif intent == 'prime_membership_inquiry':
        # MUST mention Prime subscription/membership
        prime_membership_words = ['prime membership', 'prime subscription', 'prime trial', 'prime account', 'cancel prime']
        if not any(word in text_lower for word in prime_membership_words):
            return False, f"No Prime membership keyword found. Text: '{text[:80]}...'"
    
    elif intent == 'delivery_status_inquiry':
        # MUST ask about location/timing
        delivery_words = ['where', 'when', 'tracking', 'arrive', 'delivered', 'status', 'not here', 'shipment', 'package', 'parcel', 'still unresolved', 'no clue where']
        if not any(word in text_lower for word in delivery_words):
            return False, f"No delivery location/timing keyword found. Text: '{text[:80]}...'"
    
    elif intent == 'general_inquiry':
        # STRICT: Must have explicit question OR concrete request
        # Question markers (actual questions)
        question_markers = ['how do i', 'how can i', 'how to', 'can you', 'could you', 'would you', 
                           'will you', 'what is', 'what are', 'why is', 'why did', 'why cant', 
                           'when can', 'is it possible', '?']
        # Action requests
        action_requests = ['please help', 'help me', 'need to', 'want to', 'can i', 'could i', 
                          'send me', 'give me', 'let me know']
        
        has_question = any(marker in text_lower for marker in question_markers)
        has_request = any(req in text_lower for req in action_requests)
        
        if not (has_question or has_request):
            return False, f"No question marker or explicit request. Text: '{text[:80]}...'"
        
        # Also reject delivery follow-ups (those should be delivery_status_inquiry)
        delivery_followup_phrases = ['where is', 'when will', 'still unresolved', 'no clue where', 
                                    'shipment', 'package', 'parcel', 'tracking']
        if any(phrase in text_lower for phrase in delivery_followup_phrases):
            return False, f"Delivery follow-up, not general inquiry. Text: '{text[:80]}...'"
    
    return True, "Matches intent criteria"


def build_refined_taxonomy(messages):
    """
    Build taxonomy with validated, non-overlapping examples.
    """
    print("\nClassifying messages with refined logic...")
    
    # Classify all messages
    classified = defaultdict(list)
    for msg in messages:
        intent, reason = classify_message_refined(msg['text'])
        classified[intent].append({
            'text': msg['text'],
            'reason': reason,
            'thread': msg['thread'],
        })
    
    # Print distribution
    print("\nIntent distribution:")
    total = sum(len(msgs) for msgs in classified.values())
    for intent, msgs in sorted(classified.items(), key=lambda x: -len(x[1])):
        pct = len(msgs) / total * 100
        print(f"  {intent:30s}: {len(msgs):3d} ({pct:5.1f}%)")
    
    # Define taxonomy with disambiguation rules
    taxonomy = []
    validation_failures = []
    
    # 1. DELIVERY_STATUS_INQUIRY
    delivery_msgs = classified.get('delivery_status_inquiry', [])
    if delivery_msgs:
        intent_data_temp = {
            'intent': 'delivery_status_inquiry',
            'description': 'Customer asking about delivery status, tracking, or when package will arrive. Includes impatient follow-ups.',
            'disambiguation': 'Focus on LOCATION/TIMING questions (even if customer is venting). If message mentions wrong/damaged item, classify as order_issue instead.',
            'keywords': ['where is', 'when will', 'tracking', 'delivered', 'arrive', 'shipping', 'not here', 'still waiting'],
        }
        
        # Validate and select examples
        valid_examples = []
        for msg in delivery_msgs[:10]:  # Check more than we need
            is_valid, reason = validate_example_matches_intent(msg['text'], intent_data_temp)
            if is_valid:
                valid_examples.append(msg['text'])
            else:
                validation_failures.append({
                    'text': msg['text'][:100],
                    'intended_category': 'delivery_status_inquiry',
                    'failure_reason': reason,
                })
            if len(valid_examples) >= 5:
                break
        
        intent_data_temp['examples'] = valid_examples[:5]
        taxonomy.append(intent_data_temp)
    
    # 2. ORDER_ISSUE
    order_msgs = classified.get('order_issue', [])
    if order_msgs:
        intent_data_temp = {
            'intent': 'order_issue',
            'description': 'Problem with the product itself: wrong item, missing item, damaged, or not as described',
            'disambiguation': 'Focus on PRODUCT problems. Pure delivery timing questions go to delivery_status_inquiry. Prime service complaints are NOT order issues.',
            'keywords': ['wrong item', 'damaged', 'broken', 'missing', 'not what i ordered', 'defective'],
        }
        
        valid_examples = []
        for msg in order_msgs[:10]:
            is_valid, reason = validate_example_matches_intent(msg['text'], intent_data_temp)
            if is_valid:
                valid_examples.append(msg['text'])
            else:
                validation_failures.append({
                    'text': msg['text'][:100],
                    'intended_category': 'order_issue',
                    'failure_reason': reason,
                })
            if len(valid_examples) >= 5:
                break
        
        intent_data_temp['examples'] = valid_examples[:5]
        taxonomy.append(intent_data_temp)
    
    # 3. REFUND_RETURN_REQUEST
    refund_msgs = classified.get('refund_return_request', [])
    if refund_msgs:
        intent_data_temp = {
            'intent': 'refund_return_request',
            'description': 'Customer explicitly requesting refund, return, or order cancellation',
            'disambiguation': 'MUST have explicit ask for money back or to send item back. Damaged items without refund request go to order_issue.',
            'keywords': ['refund', 'money back', 'return', 'send back', 'cancel order'],
        }
        
        valid_examples = []
        for msg in refund_msgs[:10]:
            is_valid, reason = validate_example_matches_intent(msg['text'], intent_data_temp)
            if is_valid:
                valid_examples.append(msg['text'])
            else:
                validation_failures.append({
                    'text': msg['text'][:100],
                    'intended_category': 'refund_return_request',
                    'failure_reason': reason,
                })
            if len(valid_examples) >= 5:
                break
        
        intent_data_temp['examples'] = valid_examples[:5]
        taxonomy.append(intent_data_temp)
    # 4-8: Other intents (simpler validation or skip for rare categories)
    # Payment, Account, Prime, General, Complaint
    
    payment_msgs = classified.get('payment_billing_issue', [])
    if payment_msgs:
        taxonomy.append({
            'intent': 'payment_billing_issue',
            'description': 'Issues with charges, payment methods, unauthorized transactions, or billing',
            'disambiguation': 'Focus on financial transactions, not product issues.',
            'keywords': ['charge', 'charged', 'payment', 'billing', 'unauthorized', 'credit card'],
            'examples': [msg['text'] for msg in payment_msgs[:5]],
        })
    
    account_msgs = classified.get('account_access_issue', [])
    if account_msgs:
        taxonomy.append({
            'intent': 'account_access_issue',
            'description': 'Login problems, password resets, account locked, or access issues',
            'disambiguation': 'Technical account access, not order or delivery issues.',
            'keywords': ['login', 'password', 'sign in', 'account locked', "can't access"],
            'examples': [msg['text'] for msg in account_msgs[:5]],
            'note': 'RARE INTENT (0.7%) - oversample for golden set',
        })
    
    prime_msgs = classified.get('prime_membership_inquiry', [])
    if prime_msgs:
        intent_data_temp = {
            'intent': 'prime_membership_inquiry',
            'description': 'Questions about Prime membership, subscription, benefits, or cancellation. NOT general Prime service complaints.',
            'disambiguation': 'Must explicitly mention Prime SUBSCRIPTION/MEMBERSHIP. Delivery issues are NOT Prime issues unless Prime-specific.',
            'keywords': ['prime membership', 'prime subscription', 'prime trial', 'cancel prime'],
        }
        
        valid_examples = []
        for msg in prime_msgs[:10]:
            is_valid, reason = validate_example_matches_intent(msg['text'], intent_data_temp)
            if is_valid:
                valid_examples.append(msg['text'])
            else:
                validation_failures.append({
                    'text': msg['text'][:100],
                    'intended_category': 'prime_membership_inquiry',
                    'failure_reason': reason,
                })
            if len(valid_examples) >= 5:
                break
        
        intent_data_temp['examples'] = valid_examples[:5]
        taxonomy.append(intent_data_temp)
    
    general_msgs = classified.get('general_inquiry', [])
    if general_msgs:
        taxonomy.append({
            'intent': 'general_inquiry',
            'description': 'General questions or requests with explicit question markers or concrete action requests. NOT pure venting.',
            'disambiguation': 'MUST have clear question (where/when/how/what/why) OR explicit request (help me/please/can you). NOT just topic + frustration.',
            'keywords': ['how', 'what', 'why', 'can you', 'help with', 'need to', 'please'],
            'examples': [msg['text'] for msg in general_msgs[:5]],
        })
    
    complaint_msgs = classified.get('complaint_no_action', [])
    if complaint_msgs:
        taxonomy.append({
            'intent': 'complaint_no_action',
            'description': 'Pure frustration/venting with no specific actionable request. Strong escalation candidate.',
            'disambiguation': 'No specific ask, just expressing dissatisfaction. Auto-escalate by default.',
            'keywords': ['pathetic', 'terrible', 'worst', 'disgusting', 'useless'],
            'examples': [msg['text'] for msg in complaint_msgs[:5]],
            'routing_note': 'STRONG ESCALATION CANDIDATE - no concrete resolution path',
            'note': 'RARE INTENT (0.7%) - oversample for golden set',
        })
    
    return taxonomy, classified, validation_failures


def validate_no_duplicates(taxonomy):
    """Ensure no example appears in multiple intents."""
    seen = {}
    duplicates = []
    
    for intent_data in taxonomy:
        intent = intent_data['intent']
        for example in intent_data['examples']:
            if example in seen:
                duplicates.append({
                    'example': example[:100],
                    'intent1': seen[example],
                    'intent2': intent,
                })
            else:
                seen[example] = intent
    
    return duplicates


def main():
    parser = argparse.ArgumentParser(description="Refine taxonomy with quality checks")
    parser.add_argument(
        '--sample',
        type=Path,
        default=Path('outputs/taxonomy_sample.jsonl'),
        help='Sampled threads'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('outputs/refined_taxonomy.json'),
        help='Output refined taxonomy'
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("Stage 6: Refine Taxonomy with Quality Checks")
    print("=" * 80)
    
    # Load samples
    threads = load_sampled_threads(args.sample)
    messages = extract_customer_messages(threads)
    print(f"✓ Loaded {len(messages)} customer messages")
    
    # Build refined taxonomy
    taxonomy, classified, validation_failures = build_refined_taxonomy(messages)
    
    # Report validation failures
    if validation_failures:
        print("\n" + "=" * 80)
        print(f"⚠️  VALIDATION FAILURES: {len(validation_failures)} examples rejected")
        print("=" * 80)
        for failure in validation_failures[:5]:  # Show first 5
            print(f"\n  Category: {failure['intended_category']}")
            print(f"  Text: \"{failure['text']}...\"")
            print(f"  Reason: {failure['failure_reason']}")
        if len(validation_failures) > 5:
            print(f"\n  ... and {len(validation_failures) - 5} more")
    else:
        print("\n✓ All examples passed validation")
    
    # Validate no duplicates
    duplicates = validate_no_duplicates(taxonomy)
    if duplicates:
        print("\n⚠️  WARNING: Found duplicate examples across intents:")
        for dup in duplicates:
            print(f"  '{dup['example']}...'")
            print(f"    Used in: {dup['intent1']} AND {dup['intent2']}")
    else:
        print("✓ No duplicate examples found")
    
    # Display taxonomy
    print("\n" + "=" * 80)
    print("REFINED TAXONOMY")
    print("=" * 80)
    print()
    
    for i, intent_data in enumerate(taxonomy, 1):
        print(f"{i}. {intent_data['intent'].upper()}")
        print(f"   Description: {intent_data['description']}")
        print(f"   Disambiguation: {intent_data['disambiguation']}")
        print(f"   Keywords: {', '.join(intent_data['keywords'])}")
        if intent_data.get('routing_note'):
            print(f"   Routing Note: {intent_data['routing_note']}")
        print(f"   Examples:")
        for j, ex in enumerate(intent_data['examples'][:3], 1):
            truncated = ex[:120] + "..." if len(ex) > 120 else ex
            print(f"      {j}. \"{truncated}\"")
        print()
    
    # Save
    output_data = {
        'num_intents': len(taxonomy),
        'intents': taxonomy,
        'validation': {
            'duplicate_examples': len(duplicates) == 0,
            'validation_failures': len(validation_failures),
            'has_disambiguation_rules': True,
            'account_access_added': True,
            'complaint_split_from_general': True,
            'example_validation_enabled': True,
        },
        'rare_intents_for_oversampling': [
            'account_access_issue',
            'complaint_no_action',
        ],
        'sample_size': len(messages),
    }
    
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"✓ Saved refined taxonomy to {args.output}")
    print("\n" + "=" * 80)
    print("NEXT: Review refined taxonomy, then add:")
    print("  1. Language filter (separate pipeline stage)")
    print("  2. Safety escalation rules (pre-classification check)")
    print()
    print("NOTE: Non-English messages (e.g., Devanagari text) in examples are expected")
    print("      at this stage. They will be filtered by language_filter.py BEFORE")
    print("      reaching the classifier in the real pipeline. This taxonomy derivation")
    print("      step does not apply language filtering.")
    print("=" * 80)
    
    return 0


if __name__ == "__main__":
    exit(main())
