#!/usr/bin/env python3
"""
Stage 7: Sample golden evaluation set from full AmazonHelp threads.

Stratified sampling by intent with deliberate oversampling of rare categories.
Applies language and safety filters at ingestion.

Output: 200-250 threads ready for hand-labeling.
"""

import argparse
import json
import random
from pathlib import Path
from collections import defaultdict
from tqdm import tqdm
import sys

# Add src to path for filters
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from language_filter import is_likely_english
from safety_filters import apply_safety_filters


def load_threads(threads_file):
    """Load all reconstructed threads."""
    print(f"Loading threads from {threads_file}...")
    with open(threads_file, 'r', encoding='utf-8') as f:
        threads = [json.loads(line) for line in f]
    print(f"✓ Loaded {len(threads):,} threads")
    return threads


def filter_amazonhelp_threads(all_threads):
    """Filter for AmazonHelp brand only."""
    print("\nFiltering for AmazonHelp threads...")
    brand_threads = []
    
    for thread in tqdm(all_threads, desc="Filtering"):
        brand_authors = set(
            msg['author'] for msg in thread['messages']
            if msg['author_role'] == 'brand'
        )
        if 'AmazonHelp' in brand_authors:
            brand_threads.append(thread)
    
    print(f"✓ Found {len(brand_threads):,} AmazonHelp threads")
    return brand_threads


def apply_ingestion_filters(threads):
    """
    Apply language and safety filters at ingestion.
    
    Returns:
        (filtered_threads, stats)
    """
    print("\nApplying ingestion filters (language + safety)...")
    
    filtered = []
    stats = {
        'total': len(threads),
        'english': 0,
        'non_english': 0,
        'safety_flagged': 0,
        'passed_filters': 0,
        'non_english_languages': defaultdict(int),
        'safety_reasons': defaultdict(int),
    }
    
    for thread in tqdm(threads, desc="Filtering"):
        # Get first customer message
        first_customer = next(
            (msg for msg in thread['messages'] if msg['author_role'] == 'customer'),
            None
        )
        
        if not first_customer:
            continue
        
        text = first_customer['text']
        
        # Language filter
        is_english, lang_reason = is_likely_english(text)
        if not is_english:
            stats['non_english'] += 1
            lang = lang_reason.replace(' detected', '').replace('Appears to be ', '')
            stats['non_english_languages'][lang] += 1
            continue
        
        stats['english'] += 1
        
        # Safety filter
        safety_result = apply_safety_filters(text)
        if safety_result['should_escalate']:
            stats['safety_flagged'] += 1
            for reason in safety_result['escalation_reasons']:
                stats['safety_reasons'][reason] += 1
            # Mark thread but DON'T exclude (want to see safety flagging in golden set)
            thread['safety_flagged'] = True
            thread['safety_reasons'] = safety_result['escalation_reasons']
        
        # Passed all filters
        stats['passed_filters'] += 1
        filtered.append(thread)
    
    # Print stats
    print(f"\n✓ Filtering complete:")
    print(f"  Total threads: {stats['total']:,}")
    print(f"  English: {stats['english']:,} ({stats['english']/stats['total']*100:.1f}%)")
    print(f"  Non-English: {stats['non_english']:,} ({stats['non_english']/stats['total']*100:.1f}%)")
    if stats['non_english_languages']:
        print(f"    Languages detected:")
        for lang, count in sorted(stats['non_english_languages'].items(), key=lambda x: -x[1]):
            print(f"      {lang}: {count:,}")
    print(f"  Safety flagged: {stats['safety_flagged']:,}")
    if stats['safety_reasons']:
        print(f"    Reasons:")
        for reason, count in sorted(stats['safety_reasons'].items(), key=lambda x: -x[1]):
            print(f"      {reason}: {count}")
    print(f"  Passed filters: {stats['passed_filters']:,}")
    
    return filtered, stats


def rough_intent_assignment(thread):
    """
    Rough keyword-based intent assignment for stratification ONLY.
    
    Uses SAME priority order as 06_refine_taxonomy.py to avoid dump-bucket problem.
    
    CRITICAL: This is for sampling stratification only, NOT actual classification.
    Real classification done by LLM or human labeling.
    """
    first_customer = next(
        (msg for msg in thread['messages'] if msg['author_role'] == 'customer'),
        None
    )
    
    if not first_customer:
        return 'unknown'
    
    text_lower = first_customer['text'].lower()
    
    # PRIORITY 1: Delivery status (including frustrated follow-ups)
    # Check FIRST before general_inquiry can claim "where"/"when"
    delivery_keywords = [
        'where is', 'when will', 'when is', 'tracking', 'delivered', 'arrive', 'arrived',
        'shipping', 'status', 'shipment', 'package', 'parcel',
        'not here', 'still waiting', 'still unresolved', 'no clue where', 'hasnt arrived',
        'dont have', "don't have", 'ordered weeks ago', 'ordered yesterday'
    ]
    
    has_delivery = any(kw in text_lower for kw in delivery_keywords)
    
    # Check for product problems (might override delivery)
    product_problems = ['wrong', 'damaged', 'broken', 'missing', 'defective', 'incorrect', 'faulty', 'wet parcel', 'chucked']
    has_product_problem = any(kw in text_lower for kw in product_problems)
    
    # PRIORITY 2: Product problems (override delivery)
    if has_product_problem:
        return 'order_issue'
    
    # PRIORITY 3: Delivery (including venting about delivery)
    if has_delivery:
        return 'delivery_status_inquiry'
    
    # PRIORITY 4: Explicit refund/return
    if any(kw in text_lower for kw in ['refund', 'return', 'money back', 'send back', 'cancel order']):
        return 'refund_return_request'
    
    # PRIORITY 5: Payment/billing
    if any(kw in text_lower for kw in ['charge', 'charged', 'payment', 'billing', 'unauthorized', 'credit card']):
        return 'payment_billing_issue'
    
    # PRIORITY 6: Account access
    if any(kw in text_lower for kw in ['login', 'password', 'account lock', 'sign in', 'cant access', "can't access"]):
        return 'account_access_issue'
    
    # PRIORITY 7: Prime membership (NOT service complaints)
    prime_membership_words = ['prime membership', 'prime subscription', 'cancel prime', 'prime trial']
    prime_service_complaint = ('not getting prime service' in text_lower or 
                              'not definitely getting prime service' in text_lower or
                              ('prime member' in text_lower and 'not' in text_lower and 'service' in text_lower))
    
    if any(kw in text_lower for kw in prime_membership_words) and not prime_service_complaint:
        return 'prime_membership_inquiry'
    
    # PRIORITY 8: Topic-less venting ONLY
    # If venting phrases + short + NO delivery/order/refund/payment topic
    venting_phrases = ['pathetic', 'terrible', 'worst', 'disgusting', 'useless', 'nothing yet', 'wow', 'ridiculous']
    has_venting = any(phrase in text_lower for phrase in venting_phrases)
    
    # Check if there's ANY topic (already checked delivery/order/refund/payment above)
    # If we got here and has_venting, it's topic-less
    if has_venting and len(text_lower) < 100:
        return 'complaint_no_action'
    
    # PRIORITY 9: General inquiry (only if has clear question/request)
    question_markers = ['how do i', 'how can i', 'can you', 'could you', 'what is', 'why is', '?']
    action_requests = ['help me', 'need to', 'want to', 'please help']
    
    if any(q in text_lower for q in question_markers + action_requests):
        return 'general_inquiry'
    
    # PRIORITY 10: Default - if no clear structure, likely general
    return 'general_inquiry'


def stratified_sample_with_oversampling(threads, target_size=200, rare_intents=None):
    """
    Stratified sampling with deliberate oversampling of rare intents.
    
    Target distribution:
    - Common intents: Natural proportion
    - Rare intents (account_access, complaint_no_action, prime): Oversample to ~5-10% each
    """
    if rare_intents is None:
        rare_intents = ['account_access_issue', 'complaint_no_action', 'prime_membership_inquiry']
    
    print(f"\nStratified sampling (target: {target_size} threads)...")
    
    # Group by rough intent
    by_intent = defaultdict(list)
    for thread in tqdm(threads, desc="Grouping by intent"):
        intent = rough_intent_assignment(thread)
        by_intent[intent].append(thread)
    
    # Print natural distribution
    print("\nNatural distribution:")
    total = sum(len(threads) for threads in by_intent.values())
    for intent, threads_list in sorted(by_intent.items(), key=lambda x: -len(x[1])):
        pct = len(threads_list) / total * 100
        print(f"  {intent:30s}: {len(threads_list):5,} ({pct:5.1f}%)")
    
    # Calculate samples per intent
    samples_per_intent = {}
    remaining = target_size
    
    # Rare intents: Force to ~5-10% each (10-20 samples out of 200)
    rare_sample_count = max(10, target_size // 20)  # 5% minimum
    for intent in rare_intents:
        if intent in by_intent:
            samples_per_intent[intent] = min(rare_sample_count, len(by_intent[intent]))
            remaining -= samples_per_intent[intent]
    
    # Common intents: Proportional from remaining budget
    common_intents = [i for i in by_intent.keys() if i not in rare_intents]
    common_total = sum(len(by_intent[i]) for i in common_intents)
    
    for intent in common_intents:
        if common_total > 0:
            proportion = len(by_intent[intent]) / common_total
            samples_per_intent[intent] = int(proportion * remaining)
    
    # Sample from each intent
    sampled = []
    print("\nSampling strategy:")
    for intent, target_count in sorted(samples_per_intent.items(), key=lambda x: -x[1]):
        available = len(by_intent[intent])
        actual_count = min(target_count, available)
        
        sampled_threads = random.sample(by_intent[intent], actual_count)
        sampled.extend(sampled_threads)
        
        pct_of_total = actual_count / target_size * 100
        oversample_note = " (OVERSAMPLED)" if intent in rare_intents else ""
        print(f"  {intent:30s}: {actual_count:3d} samples ({pct_of_total:5.1f}% of golden set){oversample_note}")
    
    print(f"\n✓ Sampled {len(sampled)} threads total")
    return sampled


def main():
    parser = argparse.ArgumentParser(description="Sample golden evaluation set")
    parser.add_argument(
        '--threads',
        type=Path,
        default=Path('data/processed/threads.jsonl'),
        help='All reconstructed threads'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('golden_set/unlabeled_sample.jsonl'),
        help='Output sample for labeling'
    )
    parser.add_argument(
        '--size',
        type=int,
        default=200,
        help='Target golden set size (default: 200)'
    )
    parser.add_argument(
        '--seed',
        type=int,
        default=42,
        help='Random seed for reproducibility'
    )
    
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    
    random.seed(args.seed)
    
    print("=" * 80)
    print("Stage 7: Sample Golden Evaluation Set")
    print("=" * 80)
    print()
    
    # Load all threads
    all_threads = load_threads(args.threads)
    
    # Filter for AmazonHelp
    amazonhelp_threads = filter_amazonhelp_threads(all_threads)
    
    # Apply language + safety filters
    filtered_threads, filter_stats = apply_ingestion_filters(amazonhelp_threads)
    
    # Stratified sample with rare-intent oversampling
    sampled = stratified_sample_with_oversampling(
        filtered_threads,
        target_size=args.size,
        rare_intents=['account_access_issue', 'complaint_no_action', 'prime_membership_inquiry']
    )
    
    # Save
    print(f"\nSaving to {args.output}...")
    with open(args.output, 'w', encoding='utf-8') as f:
        for thread in sampled:
            # Add metadata for labeling
            thread['sampling_metadata'] = {
                'rough_intent_for_stratification': rough_intent_assignment(thread),
                'safety_flagged': thread.get('safety_flagged', False),
                'safety_reasons': thread.get('safety_reasons', []),
            }
            f.write(json.dumps(thread) + '\n')
    
    # Also save filter stats
    stats_file = args.output.parent / 'filter_stats.json'
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(filter_stats, f, indent=2, default=str)
    
    print(f"✓ Saved {len(sampled)} threads")
    print(f"✓ Filter stats saved to {stats_file}")
    
    # Count safety-flagged threads
    safety_flagged_count = sum(1 for t in sampled if t.get('safety_flagged', False))
    if safety_flagged_count > 0:
        print(f"\n⚠️  {safety_flagged_count} threads are safety-flagged (crisis/PII/abuse/threat)")
        print(f"   These are marked in sampling_metadata.safety_flagged")
        print(f"   Review these carefully during labeling - should likely escalate")
    
    print("\n" + "=" * 80)
    print("✓ Stage 7 complete!")
    print("=" * 80)
    print()
    print("NEXT STEPS:")
    print("  1. Review unlabeled_sample.jsonl")
    print("     - Each thread has sampling_metadata.rough_intent_for_stratification")
    print("     - Safety-flagged threads marked in sampling_metadata.safety_flagged")
    print("  2. Hand-label all threads with correct intent + routing decision")
    print("     - Add 'label' field to each thread JSON")
    print("     - Include: intent, routing, routing_reason, confidence")
    print("  3. Save as golden_set/labeled.jsonl")
    print("  3. Save as golden_set/labeled.jsonl")
    print("  4. Build LLM classifier using approved_taxonomy.json")
    print("  5. Evaluate classifier on labeled golden set")
    print()
    
    return 0


if __name__ == "__main__":
    exit(main())
