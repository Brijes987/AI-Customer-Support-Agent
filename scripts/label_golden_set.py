#!/usr/bin/env python3
"""
Interactive CLI labeling tool for golden set.

Shows one conversation at a time, asks for intent + routing, saves progress.
Resume-friendly: picks up where you left off.
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime


# Load approved taxonomy for intent list
def load_taxonomy():
    """Load approved taxonomy to show intent options."""
    taxonomy_path = Path('golden_set/approved_taxonomy.json')
    if not taxonomy_path.exists():
        print("⚠️  Warning: approved_taxonomy.json not found")
        print("   Using default 8 intents")
        return None
    
    with open(taxonomy_path, 'r', encoding='utf-8') as f:
        taxonomy = json.load(f)
    return taxonomy


def display_thread(thread, idx, total):
    """Display thread in readable format."""
    print("\n" + "=" * 80)
    print(f"THREAD {idx + 1} of {total}")
    print("=" * 80)
    
    # Show safety warning if flagged
    metadata = thread.get('sampling_metadata', {})
    if metadata.get('safety_flagged', False):
        print("\n⚠️  ⚠️  ⚠️  SAFETY FLAGGED ⚠️  ⚠️  ⚠️")
        print(f"Reasons: {', '.join(metadata.get('safety_reasons', []))}")
        print("This thread likely requires ESCALATION")
        print("=" * 80)
    
    # Show rough intent suggestion
    rough_intent = metadata.get('rough_intent_for_stratification', 'unknown')
    print(f"\nSuggested intent (from sampling): {rough_intent}")
    print()
    
    # Show conversation
    messages = thread.get('messages', [])
    for i, msg in enumerate(messages, 1):
        role = "CUSTOMER" if msg['author_role'] == 'customer' else "BRAND"
        author = msg.get('author', 'unknown')
        text = msg.get('text', '')
        
        # Truncate very long messages
        if len(text) > 500:
            text = text[:500] + "... [truncated]"
        
        print(f"[{i}] {role} (@{author}):")
        print(f"    {text}")
        print()
    
    print("=" * 80)


def get_intent_choice(taxonomy):
    """Ask user to select intent."""
    print("\nSelect INTENT (1-8):")
    
    if taxonomy:
        intents = taxonomy['intents']
        for i, intent_data in enumerate(intents, 1):
            intent_name = intent_data['intent']
            description = intent_data['description'][:60]  # Truncate for display
            print(f"  {i}. {intent_name}")
            print(f"     {description}...")
    else:
        # Fallback if taxonomy not loaded
        default_intents = [
            'delivery_status_inquiry',
            'order_issue',
            'refund_return_request',
            'payment_billing_issue',
            'account_access_issue',
            'prime_membership_inquiry',
            'general_inquiry',
            'complaint_no_action',
        ]
        for i, intent in enumerate(default_intents, 1):
            print(f"  {i}. {intent}")
    
    while True:
        try:
            choice = input("\nYour choice (1-8, or 'q' to save and quit): ").strip()
            if choice.lower() == 'q':
                return None, 'quit'
            
            choice_num = int(choice)
            if 1 <= choice_num <= 8:
                if taxonomy:
                    intent_name = taxonomy['intents'][choice_num - 1]['intent']
                else:
                    intent_name = default_intents[choice_num - 1]
                return intent_name, 'ok'
            else:
                print("❌ Please enter 1-8")
        except ValueError:
            print("❌ Please enter a number 1-8, or 'q' to quit")


def get_routing_choice():
    """Ask user for routing decision."""
    print("\nRouting decision:")
    print("  1. Auto-handle (safe to handle automatically)")
    print("  2. Escalate (send to human agent)")
    
    while True:
        choice = input("\nYour choice (1 or 2): ").strip()
        if choice == '1':
            return 'auto_handle'
        elif choice == '2':
            return 'escalate'
        else:
            print("❌ Please enter 1 or 2")


def get_routing_reason():
    """Ask user for routing reason."""
    print("\nReason (one line):")
    reason = input("> ").strip()
    
    # Allow empty for auto-handle
    if not reason:
        return "Standard case"
    
    return reason


def get_confidence():
    """Ask user for labeling confidence."""
    print("\nYour confidence in this label:")
    print("  1. High (very clear)")
    print("  2. Medium (reasonable judgment)")
    print("  3. Low (uncertain/ambiguous)")
    
    while True:
        choice = input("\nConfidence (1-3, or press Enter for High): ").strip()
        if not choice or choice == '1':
            return 'high'
        elif choice == '2':
            return 'medium'
        elif choice == '3':
            return 'low'
        else:
            print("❌ Please enter 1, 2, or 3")


def save_progress(output_path, labeled_threads):
    """Save labeled threads to JSONL."""
    with open(output_path, 'w', encoding='utf-8') as f:
        for thread in labeled_threads:
            f.write(json.dumps(thread) + '\n')


def main():
    parser = argparse.ArgumentParser(
        description="Interactive labeling tool for golden set",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/label_golden_set.py
  python scripts/label_golden_set.py --resume  # Continue from where you left off
        """
    )
    parser.add_argument(
        '--input',
        type=Path,
        default=Path('golden_set/unlabeled_sample.jsonl'),
        help='Unlabeled threads'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('golden_set/labeled.jsonl'),
        help='Output labeled threads'
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Resume from existing labels (skip already labeled)'
    )
    
    args = parser.parse_args()
    
    # Load taxonomy
    taxonomy = load_taxonomy()
    
    # Load unlabeled threads
    print("Loading unlabeled threads...")
    with open(args.input, 'r', encoding='utf-8') as f:
        threads = [json.loads(line) for line in f]
    print(f"✓ Loaded {len(threads)} threads")
    
    # Load existing labels if resuming
    labeled_threads = []
    start_idx = 0
    
    if args.resume and args.output.exists():
        print("\nResuming from existing labels...")
        with open(args.output, 'r', encoding='utf-8') as f:
            labeled_threads = [json.loads(line) for line in f]
        start_idx = len(labeled_threads)
        print(f"✓ Already labeled: {start_idx} threads")
        print(f"  Starting from thread {start_idx + 1}")
    
    # Check if already complete
    if start_idx >= len(threads):
        print("\n✓ All threads already labeled!")
        print(f"   {len(labeled_threads)} labels in {args.output}")
        return 0
    
    print("\n" + "=" * 80)
    print("LABELING INSTRUCTIONS")
    print("=" * 80)
    print("For each conversation:")
    print("  1. Read the customer messages")
    print("  2. Select the correct intent (1-8)")
    print("  3. Choose routing (1=auto, 2=escalate)")
    print("  4. Provide a reason")
    print("  5. Rate your confidence")
    print()
    print("Press Ctrl+C at any time to save and exit")
    print("Type 'q' when selecting intent to save and quit")
    print("=" * 80)
    
    input("\nPress Enter to begin...")
    
    try:
        for idx in range(start_idx, len(threads)):
            thread = threads[idx]
            
            # Display thread
            display_thread(thread, idx, len(threads))
            
            # Get intent
            intent, status = get_intent_choice(taxonomy)
            if status == 'quit':
                print("\n💾 Saving progress and quitting...")
                break
            
            # Get routing
            routing = get_routing_choice()
            
            # Get reason
            reason = get_routing_reason()
            
            # Get confidence
            confidence = get_confidence()
            
            # Add label to thread
            thread['label'] = {
                'intent': intent,
                'routing': routing,
                'routing_reason': reason,
                'labeler_confidence': confidence,
                'labeled_at': datetime.now().isoformat(),
            }
            
            # Add to labeled list
            labeled_threads.append(thread)
            
            # Save progress after each label
            save_progress(args.output, labeled_threads)
            
            print(f"\n✓ Saved label {len(labeled_threads)}/{len(threads)}")
            
            # Show progress
            remaining = len(threads) - len(labeled_threads)
            if remaining > 0:
                print(f"   {remaining} threads remaining")
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        print("💾 Saving progress...")
        save_progress(args.output, labeled_threads)
    
    # Final save
    save_progress(args.output, labeled_threads)
    
    print("\n" + "=" * 80)
    print(f"✓ LABELING SESSION COMPLETE")
    print("=" * 80)
    print(f"  Total labeled: {len(labeled_threads)}/{len(threads)}")
    print(f"  Saved to: {args.output}")
    
    if len(labeled_threads) < len(threads):
        remaining = len(threads) - len(labeled_threads)
        print(f"\n  {remaining} threads remaining")
        print(f"  Resume with: python scripts/label_golden_set.py --resume")
    else:
        print("\n✓ All threads labeled!")
        print("\nNEXT STEPS:")
        print("  1. Review labeled.jsonl for consistency")
        print("  2. Build LLM classifier (scripts/08_build_llm_classifier.py)")
        print("  3. Evaluate classifier on labeled golden set")
    
    print("=" * 80)
    
    return 0


if __name__ == "__main__":
    exit(main())
