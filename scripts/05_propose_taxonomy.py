#!/usr/bin/env python3
"""
Stage 5: Analyze sampled threads and propose intent taxonomy.

Uses keyword analysis and pattern matching to identify common issue types,
then proposes 6-10 intent categories with example utterances.

This is a PROPOSAL only — human must review and confirm before use.
"""

import argparse
import json
import re
from pathlib import Path
from collections import Counter, defaultdict


def load_sampled_threads(sample_file):
    """Load sampled threads from JSONL."""
    print(f"Loading sampled threads from {sample_file}...")
    with open(sample_file, 'r', encoding='utf-8') as f:
        threads = [json.loads(line) for line in f]
    print(f"✓ Loaded {len(threads)} threads")
    return threads


def extract_initial_customer_messages(threads):
    """Extract the first customer message from each thread."""
    messages = []
    for thread in threads:
        first_customer = next(
            (msg for msg in thread['messages'] if msg['author_role'] == 'customer'),
            None
        )
        if first_customer:
            messages.append({
                'thread_id': thread['thread_id'],
                'text': first_customer['text'],
                'full_thread': thread,
            })
    return messages


def keyword_analysis(messages):
    """
    Identify common keywords and phrases in customer messages.
    Helps surface common issue patterns.
    """
    print("\nAnalyzing keywords in customer messages...")
    
    # Common support-domain keywords to look for
    keywords = {
        'delivery': ['deliver', 'shipping', 'ship', 'arrive', 'package', 'tracking', 'track', 'delivered', 'carrier'],
        'order': ['order', 'ordered', 'purchase', 'bought', 'item'],
        'refund': ['refund', 'money back', 'return', 'cancel', 'charge', 'charged'],
        'account': ['account', 'login', 'password', 'sign in', 'access'],
        'payment': ['payment', 'pay', 'credit card', 'billing', 'card', 'charge'],
        'product': ['product', 'item', 'wrong', 'broken', 'damaged', 'defect', 'missing'],
        'help': ['help', 'assist', 'support', 'need', 'can you', 'please'],
        'issue': ['issue', 'problem', 'error', 'trouble', 'not work', 'doesnt work'],
        'contact': ['contact', 'call', 'reach', 'talk to', 'speak'],
        'prime': ['prime', 'membership', 'subscription'],
    }
    
    # Count keyword occurrences
    keyword_counts = defaultdict(list)
    
    for msg in messages:
        text_lower = msg['text'].lower()
        for category, words in keywords.items():
            for word in words:
                if word in text_lower:
                    keyword_counts[category].append(msg)
                    break  # Count each message once per category
    
    # Print results
    print("\nKeyword category frequencies:")
    for category, msgs in sorted(keyword_counts.items(), key=lambda x: -len(x[1])):
        print(f"  {category:15s}: {len(msgs):3d} messages ({len(msgs)/len(messages)*100:.1f}%)")
    
    return keyword_counts


def find_question_patterns(messages):
    """Identify common question patterns."""
    print("\nAnalyzing question patterns...")
    
    patterns = {
        'where_is': r'\b(where is|where\'s|wheres)\b',
        'when_will': r'\b(when will|when can)\b',
        'how_do_i': r'\b(how do i|how can i|how to)\b',
        'why_is': r'\b(why is|why was|why did)\b',
        'can_i': r'\b(can i|could i|may i)\b',
        'what_is': r'\b(what is|what\'s|whats)\b',
        'why_cant': r'\b(why can\'t|why cant|cannot|can\'t)\b',
    }
    
    pattern_counts = defaultdict(list)
    
    for msg in messages:
        text_lower = msg['text'].lower()
        for pattern_name, regex in patterns.items():
            if re.search(regex, text_lower):
                pattern_counts[pattern_name].append(msg['text'][:100])
    
    print("\nQuestion pattern frequencies:")
    for pattern, examples in sorted(pattern_counts.items(), key=lambda x: -len(x[1])):
        print(f"  {pattern:15s}: {len(examples):3d} occurrences")
        # Show 2 examples
        for ex in examples[:2]:
            print(f"    → \"{ex}...\"")
    
    return pattern_counts


def propose_taxonomy(keyword_counts, messages):
    """
    Propose intent taxonomy based on keyword analysis.
    Returns taxonomy structure with examples.
    """
    print("\n" + "=" * 80)
    print("PROPOSED INTENT TAXONOMY")
    print("=" * 80)
    
    # Define intents based on keyword patterns
    intents = []
    
    # Intent 1: Delivery/Shipping Status
    if 'delivery' in keyword_counts and len(keyword_counts['delivery']) > 5:
        examples = [msg['text'] for msg in keyword_counts['delivery'][:5]]
        intents.append({
            'intent': 'delivery_status_inquiry',
            'description': 'Customer asking about delivery status, tracking, or shipment delays',
            'keywords': ['deliver', 'shipping', 'tracking', 'arrive', 'package'],
            'examples': examples,
        })
    
    # Intent 2: Order Issue
    order_msgs = keyword_counts.get('order', [])
    product_msgs = keyword_counts.get('product', [])
    combined_order_issue = order_msgs + product_msgs
    if len(combined_order_issue) > 5:
        examples = [msg['text'] for msg in combined_order_issue[:5]]
        intents.append({
            'intent': 'order_issue',
            'description': 'Problems with order (wrong item, missing item, damaged, not as described)',
            'keywords': ['wrong', 'missing', 'damaged', 'broken', 'not what i ordered'],
            'examples': examples,
        })
    
    # Intent 3: Refund/Return Request
    if 'refund' in keyword_counts and len(keyword_counts['refund']) > 5:
        examples = [msg['text'] for msg in keyword_counts['refund'][:5]]
        intents.append({
            'intent': 'refund_return_request',
            'description': 'Customer requesting refund, return, or order cancellation',
            'keywords': ['refund', 'return', 'cancel', 'money back'],
            'examples': examples,
        })
    
    # Intent 4: Payment/Billing Issue
    if 'payment' in keyword_counts and len(keyword_counts['payment']) > 5:
        examples = [msg['text'] for msg in keyword_counts['payment'][:5]]
        intents.append({
            'intent': 'payment_billing_issue',
            'description': 'Issues with charges, payment methods, or billing',
            'keywords': ['charge', 'payment', 'billing', 'credit card', 'unauthorized'],
            'examples': examples,
        })
    
    # Intent 5: Account Access Issue
    if 'account' in keyword_counts and len(keyword_counts['account']) > 5:
        examples = [msg['text'] for msg in keyword_counts['account'][:5]]
        intents.append({
            'intent': 'account_access_issue',
            'description': 'Login problems, password resets, account locked',
            'keywords': ['login', 'password', 'account', 'sign in', 'access'],
            'examples': examples,
        })
    
    # Intent 6: Prime/Membership Question
    if 'prime' in keyword_counts and len(keyword_counts['prime']) > 5:
        examples = [msg['text'] for msg in keyword_counts['prime'][:5]]
        intents.append({
            'intent': 'prime_membership_inquiry',
            'description': 'Questions about Prime membership, benefits, or subscription',
            'keywords': ['prime', 'membership', 'subscription', 'trial'],
            'examples': examples,
        })
    
    # Intent 7: General Inquiry (catch-all for diverse requests)
    # Sample from messages that don't fit strong categories
    categorized_thread_ids = set()
    for intent in intents:
        for ex in intent['examples']:
            # Find thread IDs for categorized messages
            for msg in messages:
                if msg['text'] == ex:
                    categorized_thread_ids.add(msg['thread_id'])
    
    uncategorized = [msg for msg in messages if msg['thread_id'] not in categorized_thread_ids]
    if uncategorized:
        examples = [msg['text'] for msg in uncategorized[:5]]
        intents.append({
            'intent': 'general_inquiry',
            'description': 'General questions, requests for information, or non-specific issues',
            'keywords': ['help', 'question', 'information', 'how', 'what'],
            'examples': examples,
        })
    
    return intents


def format_taxonomy_output(intents):
    """Format taxonomy for human review."""
    lines = []
    
    lines.append("=" * 80)
    lines.append(f"PROPOSED TAXONOMY: {len(intents)} INTENTS")
    lines.append("=" * 80)
    lines.append("")
    
    for i, intent in enumerate(intents, 1):
        lines.append(f"{i}. {intent['intent'].upper()}")
        lines.append(f"   Description: {intent['description']}")
        lines.append(f"   Keywords: {', '.join(intent['keywords'])}")
        lines.append(f"   Example utterances:")
        for j, example in enumerate(intent['examples'][:3], 1):
            truncated = example[:120] + "..." if len(example) > 120 else example
            lines.append(f"      {j}. \"{truncated}\"")
        lines.append("")
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Propose intent taxonomy from sampled threads"
    )
    parser.add_argument(
        '--sample',
        type=Path,
        default=Path('outputs/taxonomy_sample.jsonl'),
        help='Sampled threads file'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('outputs/proposed_taxonomy.json'),
        help='Output taxonomy JSON'
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("Stage 5: Propose Intent Taxonomy")
    print("=" * 80)
    print()
    
    # Load samples
    threads = load_sampled_threads(args.sample)
    
    # Extract customer messages
    messages = extract_initial_customer_messages(threads)
    print(f"✓ Extracted {len(messages)} initial customer messages")
    
    # Keyword analysis
    keyword_counts = keyword_analysis(messages)
    
    # Question pattern analysis
    question_patterns = find_question_patterns(messages)
    
    # Propose taxonomy
    intents = propose_taxonomy(keyword_counts, messages)
    
    # Display
    taxonomy_text = format_taxonomy_output(intents)
    print("\n" + taxonomy_text)
    
    # Save
    taxonomy_data = {
        'num_intents': len(intents),
        'intents': intents,
        'derived_from': str(args.sample),
        'sample_size': len(messages),
    }
    
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(taxonomy_data, f, indent=2)
    
    print(f"\n✓ Saved taxonomy to {args.output}")
    print("\n" + "=" * 80)
    print("NEXT STEPS:")
    print("  1. Review proposed taxonomy")
    print("  2. Adjust intent definitions/boundaries if needed")
    print("  3. Confirm taxonomy before proceeding to classifier")
    print("=" * 80)
    print()
    
    return 0


if __name__ == "__main__":
    exit(main())
