#!/usr/bin/env python3
"""
Stage 8: Evaluate pipeline against hand-labeled golden set.

Runs the full pipeline (classify -> retrieve -> draft -> route) on every
labeled example, compares predictions to human labels, and reports:
  - Intent classification accuracy, per-class precision/recall/F1, confusion matrix
  - Routing decision accuracy/precision/recall (auto_handle as positive class)
  - Grounding-strength distribution split by human routing label
    (used to calibrate the router's grounding threshold empirically,
    rather than guessing a number)

Usage:
    python scripts/08_evaluate.py
    python scripts/08_evaluate.py --limit 20   # quick test on first 20 labeled examples
"""

import argparse
import json
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
import os

from scripts.run_pipeline import CustomerSupportPipeline


def load_labeled_set(path: Path):
    """Load golden_set/labeled.jsonl."""
    examples = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            examples.append(json.loads(line))
    return examples


def get_customer_message(thread: dict) -> str:
    """Extract the first customer message text from a thread."""
    for msg in thread.get('messages', []):
        if msg.get('author_role') == 'customer':
            return msg.get('text', '')
    return ''


def compute_classification_metrics(y_true, y_pred, labels):
    """
    Compute accuracy, per-class precision/recall/F1, and a confusion matrix
    without relying on sklearn's exact label set assumptions.
    """
    n = len(y_true)
    correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
    accuracy = correct / n if n else 0.0

    per_class = {}
    confusion = defaultdict(lambda: defaultdict(int))

    for t, p in zip(y_true, y_pred):
        confusion[t][p] += 1

    for label in labels:
        tp = confusion[label][label]
        fp = sum(confusion[other][label] for other in labels if other != label)
        fn = sum(confusion[label][other] for other in labels if other != label)
        support = sum(confusion[label][o] for o in labels)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)
              if (precision + recall) > 0 else 0.0)

        per_class[label] = {
            'precision': round(precision, 3),
            'recall': round(recall, 3),
            'f1': round(f1, 3),
            'support': support,
        }

    macro_f1 = (sum(v['f1'] for v in per_class.values()) / len(per_class)
                if per_class else 0.0)

    return {
        'accuracy': round(accuracy, 3),
        'macro_f1': round(macro_f1, 3),
        'per_class': per_class,
        'confusion_matrix': {t: dict(preds) for t, preds in confusion.items()},
    }


def compute_routing_metrics(y_true, y_pred):
    """
    Routing metrics with 'auto_handle' as the positive class.
    Precision matters more than recall here: a wrongly auto-handled
    ticket is worse than an unnecessarily escalated one.
    """
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 'auto_handle' and p == 'auto_handle')
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 'escalate' and p == 'auto_handle')
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 'auto_handle' and p == 'escalate')
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == 'escalate' and p == 'escalate')

    n = len(y_true)
    accuracy = (tp + tn) / n if n else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        'accuracy': round(accuracy, 3),
        'auto_handle_precision': round(precision, 3),
        'auto_handle_recall': round(recall, 3),
        'auto_handle_f1': round(f1, 3),
        'confusion': {
            'true_positive_correctly_auto_handled': tp,
            'false_positive_wrongly_auto_handled': fp,
            'false_negative_wrongly_escalated': fn,
            'true_negative_correctly_escalated': tn,
        },
    }


def calibrate_grounding_threshold(results):
    """
    Look at grounding_strength distribution split by human routing label,
    to see whether the router's 0.6 threshold is well-calibrated for
    TF-IDF retrieval, or should be adjusted.

    This does NOT change the threshold automatically — it reports the
    evidence so a threshold can be chosen deliberately and documented.
    """
    auto_scores = [r['grounding_strength'] for r in results
                   if r['human_routing'] == 'auto_handle']
    escalate_scores = [r['grounding_strength'] for r in results
                        if r['human_routing'] == 'escalate']

    def summarize(scores):
        if not scores:
            return None
        return {
            'count': len(scores),
            'min': round(min(scores), 3),
            'max': round(max(scores), 3),
            'mean': round(sum(scores) / len(scores), 3),
        }

    return {
        'human_labeled_auto_handle': summarize(auto_scores),
        'human_labeled_escalate': summarize(escalate_scores),
        'note': (
            "If auto_handle examples have notably HIGHER mean grounding_strength "
            "than escalate examples, the threshold is directionally useful and "
            "just needs recalibrating to a value between the two means. If the "
            "distributions overlap heavily, grounding_strength alone is a weak "
            "signal for routing with TF-IDF and other signals (intent, confidence) "
            "should carry more weight."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate pipeline against golden set")
    parser.add_argument('--limit', type=int, default=None,
                         help='Only evaluate first N labeled examples (for quick testing)')
    parser.add_argument('--labeled-path', type=Path,
                         default=Path('golden_set/labeled.jsonl'))
    parser.add_argument('--output', type=Path,
                         default=Path('outputs/eval_results.json'))
    parser.add_argument('--no-cache', action='store_true',
                         help='Disable pipeline caching (force fresh API calls)')
    args = parser.parse_args()

    load_dotenv()
    gemini_api_key = os.getenv('GOOGLE_API_KEY')
    groq_api_key = os.getenv('GROQ_API_KEY')

    if not gemini_api_key or not groq_api_key:
        print("Missing GOOGLE_API_KEY or GROQ_API_KEY in .env")
        return 1

    print("Loading labeled golden set...")
    labeled = load_labeled_set(args.labeled_path)
    if args.limit:
        labeled = labeled[:args.limit]
    print(f"Loaded {len(labeled)} labeled examples")

    if not labeled:
        print("No labeled examples found. Check golden_set/labeled.jsonl.")
        return 1

    print("\nInitializing pipeline...")
    pipeline = CustomerSupportPipeline(
        taxonomy_path=Path('golden_set/approved_taxonomy.json'),
        threads_path=Path('data/processed/threads.jsonl'),
        golden_set_path=Path('golden_set/unlabeled_sample.jsonl'),
        cache_dir=Path('cache/pipeline'),
        gemini_api_key=gemini_api_key,
        groq_api_key=groq_api_key,
    )

    print(f"\nRunning pipeline on {len(labeled)} examples...\n")
    results = []
    for i, thread in enumerate(labeled, 1):
        customer_message = get_customer_message(thread)
        human_label = thread.get('label', {})

        if not customer_message or not human_label:
            print(f"[{i}/{len(labeled)}] SKIPPED (missing message or label)")
            continue

        print(f"[{i}/{len(labeled)}] {customer_message[:60]!r}")

        try:
            prediction = pipeline.process(
                customer_message,
                use_cache=not args.no_cache,
            )
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

        results.append({
            'thread_id': thread.get('thread_id'),
            'customer_message': customer_message,
            'human_intent': human_label.get('intent'),
            'predicted_intent': prediction['intent'],
            'intent_confidence': prediction['intent_confidence'],
            'human_routing': human_label.get('routing'),
            'predicted_routing': prediction['routing'],
            'routing_reason': prediction['routing_reason'],
            'grounding_strength': prediction['grounding_strength'],
            'drafted_reply': prediction['drafted_reply'],
            'human_routing_reason': human_label.get('routing_reason'),
            'labeler_confidence': human_label.get('labeler_confidence'),
        })

    print(f"\n{'=' * 80}")
    print(f"Evaluated {len(results)} examples successfully")
    print('=' * 80)

    # Intent classification metrics
    all_intents = sorted(set(
        [r['human_intent'] for r in results] + [r['predicted_intent'] for r in results]
    ))
    intent_metrics = compute_classification_metrics(
        [r['human_intent'] for r in results],
        [r['predicted_intent'] for r in results],
        all_intents,
    )

    print("\n--- INTENT CLASSIFICATION ---")
    print(f"Accuracy: {intent_metrics['accuracy']}")
    print(f"Macro F1: {intent_metrics['macro_f1']}")
    print("\nPer-class:")
    for label, m in intent_metrics['per_class'].items():
        print(f"  {label:30s} P={m['precision']:.3f} R={m['recall']:.3f} "
              f"F1={m['f1']:.3f} (n={m['support']})")

    # Routing metrics
    routing_metrics = compute_routing_metrics(
        [r['human_routing'] for r in results],
        [r['predicted_routing'] for r in results],
    )

    print("\n--- ROUTING DECISION ---")
    print(f"Accuracy: {routing_metrics['accuracy']}")
    print(f"Auto-handle Precision: {routing_metrics['auto_handle_precision']}")
    print(f"Auto-handle Recall: {routing_metrics['auto_handle_recall']}")
    print(f"Auto-handle F1: {routing_metrics['auto_handle_f1']}")
    print(f"Confusion: {routing_metrics['confusion']}")

    # Grounding threshold calibration
    calibration = calibrate_grounding_threshold(results)
    print("\n--- GROUNDING THRESHOLD CALIBRATION ---")
    print(f"Human-labeled AUTO_HANDLE examples: {calibration['human_labeled_auto_handle']}")
    print(f"Human-labeled ESCALATE examples: {calibration['human_labeled_escalate']}")
    print(f"\n{calibration['note']}")

    # Save everything
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output_data = {
        'n_examples': len(results),
        'intent_metrics': intent_metrics,
        'routing_metrics': routing_metrics,
        'grounding_calibration': calibration,
        'raw_results': results,
    }
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2)

    print(f"\n✓ Full results saved to {args.output}")
    return 0


if __name__ == "__main__":
    exit(main())
