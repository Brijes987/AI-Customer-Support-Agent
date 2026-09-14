#!/usr/bin/env python3
"""
Stage 4: Sample AmazonHelp threads to derive intent taxonomy.

Samples a stratified set of threads (by length, resolution status) and displays
customer messages with brand resolutions to ground taxonomy in real data.

Does NOT define intents — just shows representative examples for human review.
"""

import argparse
import json
import random
from pathlib import Path
from collections import defaultdict
from tqdm import tqdm


def load_threads(threads_file):
    """Load reconstructed threads from JSON."""
    print(f"Loading threads from {threads_file}...")
    with open(threads_file, 'r', encoding='utf-8') as f:
        threads = [json.loads(line) for line in f]
    print(f"✓ Loaded {len(threads):,} threads")
    return threads


def filter_brand_threads(all_threads, brand_name):
    """Filter threads for a specific brand."""
    print(f"\nFiltering threads for brand: {brand_name}")
    brand_threads = []
    
    for thread in tqdm(all_threads, desc="Filtering"):
        # Check if any brand message is from this brand
        brand_authors = set(
            msg['author'] for msg in thread['messages']
            if msg['author_role'] == 'brand'
        )
        if brand_name in brand_authors:
            brand_threads.append(thread)
    
    print(f"✓ Found {len(brand_threads):,} threads for {brand_name}")
    return brand_threads


def categorize_threads(threads):
    """
    Categorize threads by characteristics for stratified sampling.
    
    Categories:
    - Thread length (short: 2-3, medium: 4-6, long: 7+)
    - Resolution status (resolved: ends with brand, unresolved: ends with customer)
    - Engagement (single-turn vs multi-turn brand responses)
    """
    categories = defaultdict(list)
    
    for thread in threads:
        length = len(thread['messages'])
        last_msg = thread['messages'][-1] if thread['messages'] else None
        
        # Length category
        if length <= 3:
            length_cat = 'short'
        elif length <= 6:
            length_cat = 'medium'
        else:
            length_cat = 'long'
        
        # Resolution status
        if last_msg and last_msg['author_role'] == 'brand':
            resolution_cat = 'resolved'
        else:
            resolution_cat = 'unresolved'
        
        # Engagement depth
        brand_response_count = sum(
            1 for msg in thread['messages'] if msg['author_role'] == 'brand'
        )
        engagement_cat = 'multi_turn' if brand_response_count >= 2 else 'single_turn'
        
        # Combined category key
        cat_key = f"{length_cat}_{resolution_cat}_{engagement_cat}"
        categories[cat_key].append(thread)
    
    return categories


def stratified_sample(categories, total_samples=100):
    """
    Sample threads from each category proportionally.
    Ensures diversity across thread types.
    """
    print(f"\nStratified sampling (target: {total_samples} threads)...")
    print(f"Found {len(categories)} categories")
    
    # Calculate samples per category (proportional to size)
    total_threads = sum(len(threads) for threads in categories.values())
    samples = []
    
    for cat_key, threads in sorted(categories.items()):
        # Proportional allocation
        proportion = len(threads) / total_threads
        n_samples = max(1, int(proportion * total_samples))  # At least 1 per category
        
        # Sample (or take all if fewer than n_samples)
        sampled = random.sample(threads, min(n_samples, len(threads)))
        samples.extend(sampled)
        
        print(f"  {cat_key}: {len(threads):,} threads → sampled {len(sampled)}")
    
    # If we're over target, randomly trim
    if len(samples) > total_samples:
        samples = random.sample(samples, total_samples)
    
    print(f"\n✓ Sampled {len(samples)} threads total")
    return samples


def format_thread_for_display(thread, idx):
    """Format a thread for human-readable display."""
    lines = []
    lines.append("=" * 80)
    lines.append(f"THREAD {idx + 1} (ID: {thread['thread_id']}, {len(thread['messages'])} messages)")
    lines.append("=" * 80)
    
    for i, msg in enumerate(thread['messages'], 1):
        role_label = "CUSTOMER" if msg['author_role'] == 'customer' else "BRAND"
        lines.append(f"\n[{i}] {role_label} (@{msg['author']}):")
        
        # Wrap text at 76 chars for readability
        text = msg['text']
        if len(text) > 500:
            text = text[:500] + "... [truncated]"
        
        lines.append(f"    {text}")
    
    lines.append("")
    return "\n".join(lines)


def extract_customer_intents_preview(threads, n_show=30):
    """
    Extract just the initial customer messages for quick scanning.
    Helps identify common issue patterns.
    """
    print(f"\n{'=' * 80}")
    print(f"INITIAL CUSTOMER MESSAGES (first {n_show} sampled threads)")
    print(f"{'=' * 80}\n")
    
    for i, thread in enumerate(threads[:n_show], 1):
        # Find first customer message
        first_customer = next(
            (msg for msg in thread['messages'] if msg['author_role'] == 'customer'),
            None
        )
        
        if first_customer:
            text = first_customer['text']
            if len(text) > 120:
                text = text[:120] + "..."
            print(f"{i:2d}. {text}")
    
    print(f"\n{'=' * 80}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Sample threads for intent taxonomy derivation"
    )
    parser.add_argument(
        '--threads',
        type=Path,
        default=Path('data/processed/threads.jsonl'),
        help='Path to all threads'
    )
    parser.add_argument(
        '--brand',
        type=str,
        default='AmazonHelp',
        help='Brand to filter for'
    )
    parser.add_argument(
        '--sample-size',
        type=int,
        default=100,
        help='Number of threads to sample'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('outputs/taxonomy_sample.jsonl'),
        help='Output file for sampled threads'
    )
    parser.add_argument(
        '--display-file',
        type=Path,
        default=Path('outputs/taxonomy_sample_display.txt'),
        help='Human-readable display file'
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
    print("Stage 4: Sample Threads for Taxonomy Derivation")
    print("=" * 80)
    print()
    
    # Load all threads
    all_threads = load_threads(args.threads)
    
    # Filter for brand
    brand_threads = filter_brand_threads(all_threads, args.brand)
    
    if not brand_threads:
        print(f"❌ No threads found for brand: {args.brand}")
        return 1
    
    # Categorize
    print("\nCategorizing threads for stratified sampling...")
    categories = categorize_threads(brand_threads)
    
    # Sample
    sampled = stratified_sample(categories, total_samples=args.sample_size)
    
    # Show quick preview of initial customer messages
    extract_customer_intents_preview(sampled, n_show=30)
    
    # Save sampled threads (JSONL for downstream processing)
    print(f"Saving sampled threads to {args.output}...")
    with open(args.output, 'w', encoding='utf-8') as f:
        for thread in sampled:
            f.write(json.dumps(thread) + '\n')
    print(f"✓ Saved {len(sampled)} threads")
    
    # Save human-readable display
    print(f"\nGenerating human-readable display file...")
    with open(args.display_file, 'w', encoding='utf-8') as f:
        f.write(f"AMAZONHELP THREAD SAMPLE FOR TAXONOMY DERIVATION\n")
        f.write(f"Generated from {len(brand_threads):,} total threads\n")
        f.write(f"Stratified sample size: {len(sampled)}\n")
        f.write(f"Random seed: {args.seed}\n")
        f.write(f"\n{'=' * 80}\n\n")
        
        # Quick preview section
        f.write("QUICK SCAN: Initial Customer Messages (first 50)\n")
        f.write("=" * 80 + "\n\n")
        for i, thread in enumerate(sampled[:50], 1):
            first_customer = next(
                (msg for msg in thread['messages'] if msg['author_role'] == 'customer'),
                None
            )
            if first_customer:
                text = first_customer['text']
                if len(text) > 150:
                    text = text[:150] + "..."
                f.write(f"{i:3d}. {text}\n")
        
        f.write(f"\n{'=' * 80}\n")
        f.write(f"\nFULL THREAD DETAILS (showing first 30 complete threads)\n\n")
        
        # Full thread details for deeper analysis
        for i, thread in enumerate(sampled[:30]):
            f.write(format_thread_for_display(thread, i))
    
    print(f"✓ Saved to {args.display_file}")
    
    print("\n" + "=" * 80)
    print("✓ Stage 4 complete!")
    print("=" * 80)
    print()
    print("NEXT STEPS:")
    print(f"  1. Review {args.display_file}")
    print(f"  2. Identify 6-10 common issue patterns (intents)")
    print(f"  3. Define taxonomy with example utterances per intent")
    print(f"  4. Confirm taxonomy before building classifier")
    print()
    
    return 0


if __name__ == "__main__":
    exit(main())
