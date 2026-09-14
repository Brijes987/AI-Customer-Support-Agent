#!/usr/bin/env python3
"""
Stage 2: Reconstruct conversation threads from raw Twitter data.

Uses in_response_to_tweet_id and response_tweet_id to chain messages into threads.
Critical for evaluation — misreconstructed threads will contaminate intent/response quality.
"""

import argparse
import json
import sys
from pathlib import Path
from collections import defaultdict
import pandas as pd
from tqdm import tqdm


def find_csv_path(default_path):
    """
    Find the actual CSV path, checking:
    1. The provided default path
    2. The data manifest (written by stage 1)
    3. Common nested locations
    
    Returns the first existing path found, or the default if none exist.
    """
    # Try manifest first
    manifest_path = Path("data/data_manifest.json")
    if manifest_path.exists():
        try:
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
                csv_path = Path(manifest['csv_path'])
                if csv_path.exists():
                    print(f"✓ Using CSV path from manifest: {csv_path}")
                    return csv_path
        except (json.JSONDecodeError, KeyError) as e:
            print(f"⚠️  Warning: Could not read manifest ({e})")
    
    # Try default path
    if default_path.exists():
        print(f"✓ Using default CSV path: {default_path}")
        return default_path
    
    # Try common nested locations
    alternatives = [
        Path("data/raw/twcs/twcs.csv"),
        Path("data/raw/twcs.csv"),
    ]
    
    for alt in alternatives:
        if alt.exists():
            print(f"✓ Found CSV at: {alt}")
            return alt
    
    # If nothing found, return default and let it fail with clear error
    print(f"❌ CSV file not found. Tried:")
    print(f"   - Manifest: {manifest_path}")
    print(f"   - Default: {default_path}")
    for alt in alternatives:
        print(f"   - Alternative: {alt}")
    print()
    print("Did you run: python scripts/01_download_data.py ?")
    return default_path



def build_thread_graph(df):
    """
    Build adjacency graph from reply relationships.
    
    Returns:
        tweets: dict mapping tweet_id -> tweet row dict
        children: dict mapping tweet_id -> list of child tweet_ids
    """
    print("Building thread graph...")
    
    tweets = {}
    children = defaultdict(list)
    
    for idx, row in tqdm(df.iterrows(), total=len(df), desc="Processing tweets"):
        tweet_id = str(row['tweet_id'])
        tweets[tweet_id] = row.to_dict()
        
        # Track reply relationship
        parent_id = row.get('in_response_to_tweet_id')
        if pd.notna(parent_id):
            parent_id = str(int(parent_id))
            children[parent_id].append(tweet_id)
    
    return tweets, children


def reconstruct_thread(root_id, tweets, children, visited):
    """
    Reconstruct a single conversation thread via DFS traversal.
    
    Returns a thread dict with messages in chronological order.
    """
    if root_id in visited:
        return None
    
    messages = []
    stack = [(root_id, 0)]  # (tweet_id, depth)
    local_visited = set()
    
    while stack:
        tweet_id, depth = stack.pop()
        
        if tweet_id in local_visited or tweet_id not in tweets:
            continue
        
        local_visited.add(tweet_id)
        visited.add(tweet_id)
        
        tweet = tweets[tweet_id]
        
        # Determine author role (customer vs brand)
        # inbound column: True if customer -> brand
        is_inbound = tweet.get('inbound', False)
        author_role = 'customer' if is_inbound else 'brand'
        
        messages.append({
            'tweet_id': tweet_id,
            'author': tweet.get('author_id', ''),
            'author_role': author_role,
            'text': tweet.get('text', ''),
            'created_at': tweet.get('created_at', ''),
            'depth': depth,
        })
        
        # Add children to stack (in reverse order for DFS to process in order)
        child_ids = children.get(tweet_id, [])
        for child_id in reversed(child_ids):
            if child_id not in local_visited:
                stack.append((child_id, depth + 1))
    
    # Sort messages chronologically
    messages.sort(key=lambda m: m['created_at'])
    
    return {
        'thread_id': root_id,
        'message_count': len(messages),
        'messages': messages,
    }


def find_thread_roots(tweets, children):
    """
    Identify root tweets (those not replying to anything, or replying to external tweets).
    """
    print("Finding thread roots...")
    roots = []
    
    for tweet_id, tweet in tqdm(tweets.items(), desc="Identifying roots"):
        parent_id = tweet.get('in_response_to_tweet_id')
        
        # Root if no parent, or parent is outside our dataset
        if pd.isna(parent_id):
            roots.append(tweet_id)
        else:
            parent_id = str(int(parent_id))
            if parent_id not in tweets:
                roots.append(tweet_id)
    
    print(f"✓ Found {len(roots):,} thread roots")
    return roots


def main():
    parser = argparse.ArgumentParser(description="Reconstruct conversation threads")
    parser.add_argument(
        '--input',
        type=Path,
        default=Path('data/raw/twcs.csv'),
        help='Path to raw CSV file'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('data/processed/threads.jsonl'),
        help='Output path for threads (JSONL format)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of rows to process (for testing)'
    )
    
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    
    print("=" * 70)
    print("Stage 2: Thread Reconstruction")
    print("=" * 70)
    print()
    
    # Find actual CSV location (may be nested in subdirectory)
    csv_path = find_csv_path(args.input)
    
    # Load data
    print(f"\nLoading data from {csv_path}...")
    try:
        df = pd.read_csv(csv_path, nrows=args.limit)
        print(f"✓ Loaded {len(df):,} tweets")
    except FileNotFoundError:
        print(f"\n❌ File not found: {csv_path}")
        print("\nMake sure you've run: python scripts/01_download_data.py")
        sys.exit(1)
    print()
    
    # Build graph
    tweets, children = build_thread_graph(df)
    
    # Find roots
    roots = find_thread_roots(tweets, children)
    
    # Reconstruct threads
    print(f"\nReconstructing threads from {len(roots):,} roots...")
    threads = []
    visited = set()
    
    for root_id in tqdm(roots, desc="Building threads"):
        thread = reconstruct_thread(root_id, tweets, children, visited)
        if thread and thread['message_count'] > 0:
            threads.append(thread)
    
    print(f"\n✓ Reconstructed {len(threads):,} threads")
    
    # Statistics
    message_counts = [t['message_count'] for t in threads]
    avg_length = sum(message_counts) / len(message_counts) if message_counts else 0
    
    print("\nThread statistics:")
    print(f"  Total threads: {len(threads):,}")
    print(f"  Total messages: {sum(message_counts):,}")
    print(f"  Avg messages/thread: {avg_length:.2f}")
    print(f"  Min length: {min(message_counts) if message_counts else 0}")
    print(f"  Max length: {max(message_counts) if message_counts else 0}")
    
    # Save threads
    print(f"\nSaving threads to {args.output}...")
    with open(args.output, 'w', encoding='utf-8') as f:
        for thread in threads:
            f.write(json.dumps(thread) + '\n')
    
    print(f"✓ Saved {len(threads):,} threads")
    print()
    print("=" * 70)
    print("✓ Stage 2 complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
