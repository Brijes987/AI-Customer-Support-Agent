#!/usr/bin/env python3
"""
Stage 3: Analyze brand candidates for selection.

Evaluates brands by:
- Total volume (inbound customer messages)
- ACTUAL response rate (including unreplied threads from raw CSV)
- Average thread length
- Reply diversity (unique reply texts or embedding clusters)
- Resolution rate

Outputs a shortlist with justification for picking one brand.
"""

import argparse
import json
import sys
import re
from pathlib import Path
from collections import defaultdict, Counter
import pandas as pd
from tqdm import tqdm


def normalize_reply_for_template_matching(text):
    """
    Normalize a reply to detect template similarity by removing personalized elements.
    
    Strips:
    - @mentions (e.g., @username)
    - URLs (http/https links)
    - Numbers (likely confirmation IDs, ticket numbers, phone numbers)
    - Extra whitespace
    
    This lets us detect "Hi @user, your order #12345 is ready" and 
    "Hi @other, your order #67890 is ready" as the same template.
    """
    normalized = text.lower()
    
    # Remove @mentions
    normalized = re.sub(r'@\w+', '@USER', normalized)
    
    # Remove URLs
    normalized = re.sub(r'https?://\S+', 'URL', normalized)
    
    # Remove numbers (but keep common words like "24/7")
    # Replace sequences of 3+ digits with a placeholder
    normalized = re.sub(r'\b\d{3,}\b', 'NUM', normalized)
    
    # Remove standalone single/double digits that aren't part of common phrases
    # (keeps "24/7", removes standalone order numbers)
    normalized = re.sub(r'\b\d{1,2}\b(?!/)', 'N', normalized)
    
    # Collapse multiple spaces
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    return normalized


def load_threads(threads_file):
    """Load reconstructed threads from JSON."""
    print(f"Loading threads from {threads_file}...")
    with open(threads_file, 'r', encoding='utf-8') as f:
        threads = [json.loads(line) for line in f]
    print(f"✓ Loaded {len(threads):,} threads")
    return threads


def analyze_brand(brand_name, brand_threads):
    """
    Analyze a single brand's support quality metrics.
    
    Key fix: Instead of "response rate" (which is 100% by construction since
    we only have threads with responses), measure "engagement depth" metrics
    that actually differentiate brands.
    """
    
    total_threads = len(brand_threads)
    
    # Count inbound customer messages
    inbound_count = sum(
        len([msg for msg in thread['messages'] if msg['author_role'] == 'customer'])
        for thread in brand_threads
    )
    
    # Collect all brand responses for diversity analysis
    brand_replies = []
    brand_replies_raw = []  # Keep raw for display
    for thread in brand_threads:
        for msg in thread['messages']:
            if msg['author_role'] == 'brand':
                brand_replies_raw.append(msg['text'])
                # Normalize for template matching
                brand_replies.append(normalize_reply_for_template_matching(msg['text']))
    
    total_brand_responses = len(brand_replies)
    
    # REPLY DIVERSITY METRIC (FIXED)
    # Count unique TEMPLATES (after normalization), not unique exact strings
    unique_templates = len(set(brand_replies))
    template_diversity_ratio = unique_templates / total_brand_responses if total_brand_responses > 0 else 0
    
    # Count most common TEMPLATES (to detect heavy templating)
    template_counts = Counter(brand_replies)
    most_common_templates = template_counts.most_common(10)
    top_5_template_concentration = (
        sum(count for _, count in most_common_templates[:5]) / total_brand_responses 
        if total_brand_responses > 0 else 0
    )
    
    # Map normalized templates back to raw examples for display
    template_to_raw_examples = defaultdict(list)
    for raw, normalized in zip(brand_replies_raw, brand_replies):
        if len(template_to_raw_examples[normalized]) < 2:  # Keep 2 examples per template
            template_to_raw_examples[normalized].append(raw)
    
    most_common_templates_with_examples = []
    for template, count in most_common_templates[:5]:
        percentage = count / total_brand_responses
        raw_examples = template_to_raw_examples[template]
        most_common_templates_with_examples.append({
            'template': template[:200],  # Normalized template (truncated)
            'count': count,
            'percentage': percentage,
            'raw_examples': [ex[:150] for ex in raw_examples[:2]],  # Show 2 raw examples
        })
    
    # Thread length statistics
    thread_lengths = [len(thread['messages']) for thread in brand_threads]
    avg_length = sum(thread_lengths) / len(thread_lengths) if thread_lengths else 0
    
    # Multi-turn threads (at least 2 brand responses) - measures engagement depth
    multi_turn_threads = sum(
        1 for thread in brand_threads
        if sum(1 for msg in thread['messages'] if msg['author_role'] == 'brand') >= 2
    )
    multi_turn_rate = multi_turn_threads / total_threads if total_threads > 0 else 0
    
    # Resolution indicators (threads ending with brand response)
    resolved_threads = sum(
        1 for thread in brand_threads
        if thread['messages'] and thread['messages'][-1]['author_role'] == 'brand'
    )
    resolution_rate = resolved_threads / total_threads if total_threads > 0 else 0
    
    # Brand response ratio: avg brand messages per thread (engagement intensity)
    avg_brand_responses_per_thread = (
        total_brand_responses / total_threads if total_threads > 0 else 0
    )
    
    return {
        'brand': brand_name,
        'total_threads': total_threads,
        'inbound_messages': inbound_count,
        'total_brand_responses': total_brand_responses,
        'avg_brand_responses_per_thread': avg_brand_responses_per_thread,
        'avg_thread_length': avg_length,
        'multi_turn_threads': multi_turn_threads,
        'multi_turn_rate': multi_turn_rate,
        'resolved_threads': resolved_threads,
        'resolution_rate': resolution_rate,
        # FIXED: Template diversity (not exact-string uniqueness)
        'unique_templates': unique_templates,
        'template_diversity_ratio': template_diversity_ratio,
        'top_5_template_concentration': top_5_template_concentration,
        'most_common_templates': most_common_templates_with_examples,
    }


def score_brand(stats):
    """
    Score a brand for suitability as the assignment target.
    
    Criteria (updated to use metrics with real variance):
    - High volume (more data = better taxonomy, more train/eval split headroom)
    - High multi-turn rate (deep engagement, not just single automated responses)
    - Reasonable thread lengths (too short = templated, too long = complex outliers)
    - High resolution rate (threads that actually close with brand response)
    - Decent reply diversity (need variation for RAG to be meaningful)
    """
    score = 0
    
    # Volume score (logarithmic, saturates at 10k threads)
    volume_score = min(stats['total_threads'] / 10000, 1.0) * 30
    score += volume_score
    
    # Multi-turn engagement score (replaces broken "response rate")
    # This measures deep engagement: do they go back-and-forth or just auto-reply once?
    multi_turn_score = stats['multi_turn_rate'] * 30
    score += multi_turn_score
    
    # Thread length score (penalize too short or too long, sweet spot 2-6)
    length = stats['avg_thread_length']
    if 2 <= length <= 6:
        length_score = 20
    elif length < 2:
        length_score = 10 * length  # Penalize very short
    else:
        length_score = 20 * (1 - min((length - 6) / 10, 1))  # Penalize very long
    score += length_score
    
    # Resolution rate score
    resolution_score = stats['resolution_rate'] * 20
    score += resolution_score
    
    return score


def main():
    parser = argparse.ArgumentParser(description="Analyze brands for selection")
    parser.add_argument(
        '--threads',
        type=Path,
        default=Path('data/processed/threads.jsonl'),
        help='Path to reconstructed threads file'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('outputs/brand_analysis.json'),
        help='Output path for analysis results'
    )
    parser.add_argument(
        '--top-n',
        type=int,
        default=10,
        help='Number of top brands to analyze in detail'
    )
    
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    
    print("=" * 70)
    print("Stage 3: Brand Analysis")
    print("=" * 70)
    print()
    
    # Load threads
    threads = load_threads(args.threads)
    
    # Group by brand
    print("\nGrouping threads by brand...")
    brands = defaultdict(list)
    for thread in threads:
        # Brand is the author of non-customer messages
        brand_authors = set(
            msg['author'] for msg in thread['messages']
            if msg['author_role'] == 'brand'
        )
        if brand_authors:
            # Use the first brand author (usually there's only one per thread)
            brand = sorted(brand_authors)[0]
            brands[brand].append(thread)
    
    print(f"✓ Found {len(brands)} brands")
    
    # Quick volume ranking
    brand_volumes = {brand: len(threads) for brand, threads in brands.items()}
    top_brands_by_volume = sorted(brand_volumes.items(), key=lambda x: -x[1])[:args.top_n]
    
    print(f"\nAnalyzing top {args.top_n} brands by volume...")
    print()
    
    # Detailed analysis of top brands
    results = []
    for brand, _ in tqdm(top_brands_by_volume, desc="Analyzing brands"):
        brand_threads = brands[brand]
        stats = analyze_brand(brand, brand_threads)
        stats['score'] = score_brand(stats)
        results.append(stats)
    
    # Sort by score
    results.sort(key=lambda x: -x['score'])
    
    # Display results
    print("\n" + "=" * 70)
    print("BRAND ANALYSIS RESULTS (ranked by suitability score)")
    print("=" * 70)
    print()
    
    for i, stats in enumerate(results, 1):
        print(f"{i}. {stats['brand']}")
        print(f"   Score: {stats['score']:.1f}/100")
        print(f"   Total threads: {stats['total_threads']:,}")
        print(f"   Inbound messages: {stats['inbound_messages']:,}")
        print(f"   Brand responses: {stats['total_brand_responses']:,} ({stats['avg_brand_responses_per_thread']:.2f} per thread)")
        print(f"   Avg thread length: {stats['avg_thread_length']:.1f} messages")
        print(f"   Multi-turn threads: {stats['multi_turn_threads']:,} ({stats['multi_turn_rate']:.1%})")
        print(f"   Resolution rate: {stats['resolution_rate']:.1%}")
        print(f"   Template diversity: {stats['template_diversity_ratio']:.1%} unique ({stats['unique_templates']:,}/{stats['total_brand_responses']:,} templates)")
        print(f"   Top-5 template concentration: {stats['top_5_template_concentration']:.1%}")
        print()
    
    # Save results
    output_data = {
        'analysis_summary': {
            'total_brands': len(brands),
            'analyzed_brands': len(results),
            'recommendation': results[0]['brand'] if results else None,
        },
        'brand_rankings': results,
    }
    
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2)
    
    print("=" * 70)
    print(f"✓ Results saved to {args.output}")
    print("=" * 70)
    print()
    
    if results:
        print("RECOMMENDED BRAND:")
        print(f"  {results[0]['brand']}")
        print()
        print("JUSTIFICATION:")
        top = results[0]
        print(f"  • High volume: {top['total_threads']:,} threads")
        print(f"  • Strong multi-turn engagement: {top['multi_turn_rate']:.1%}")
        print(f"  • Good thread length: {top['avg_thread_length']:.1f} avg messages")
        print(f"  • High resolution rate: {top['resolution_rate']:.1%}")
        print(f"  • Template diversity: {top['template_diversity_ratio']:.1%} unique templates")
        print()
        print("TEMPLATE DIVERSITY DETAIL:")
        print(f"  • Total responses: {top['total_brand_responses']:,}")
        print(f"  • Unique templates: {top['unique_templates']:,}")
        print(f"  • Top 5 templates account for: {top['top_5_template_concentration']:.1%} of all replies")
        if top.get('most_common_templates'):
            print(f"  • Most common templates (normalized, with raw examples):")
            for i, tmpl in enumerate(top['most_common_templates'][:3], 1):
                print(f"\n    {i}. Template ({tmpl['percentage']:.1%} of replies):")
                print(f"       Normalized: \"{tmpl['template']}\"")
                print(f"       Raw examples:")
                for j, example in enumerate(tmpl['raw_examples'], 1):
                    truncated = example[:100] + "..." if len(example) > 100 else example
                    print(f"         {j}. \"{truncated}\"")
        print()


if __name__ == "__main__":
    main()
