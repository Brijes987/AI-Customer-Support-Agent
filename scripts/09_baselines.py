#!/usr/bin/env python3
"""
Stage 9: Baseline comparisons.

Computes two baselines against the hand-labeled golden set, using the
exact same metrics as the real pipeline (see 08_evaluate.py), so headline
numbers can be compared apples-to-apples.

BASELINE 1 - Trivial:
    Intent: always predict the single most common intent in the golden set.
    Routing: always predict the single most common routing decision.
    (No reasoning, no model, no keywords - the "dumbest possible" system.)

BASELINE 2 - Simple:
    Intent: keyword/rule-based classifier (no LLM).
    Routing: rule-based on keyword-matched intent + safety/language checks.
    (A basic system a junior engineer might build in an afternoon,
    with no machine learning at all.)

Both baselines run entirely locally - no API calls, no quota risk.

Usage:
    python scripts/09_baselines.py
"""

import json
import re
from pathlib import Path
from collections import Counter, defaultdict


def load_labeled_set(path: Path):
    examples = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            examples.append(json.loads(line))
    return examples


def get_customer_message(thread: dict) -> str:
    for msg in thread.get('messages', []):
        if msg.get('author_role') == 'customer':
            return msg.get('text', '')
    return ''


def compute_classification_metrics(y_true, y_pred, labels):
    n = len(y_true)
    correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
    accuracy = correct / n if n else 0.0

    confusion = defaultdict(lambda: defaultdict(int))
    for t, p in zip(y_true, y_pred):
        confusion[t][p] += 1

    per_class = {}
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

    macro_f1 = sum(v['f1'] for v in per_class.values()) / len(per_class) if per_class else 0.0
    weighted_f1 = (sum(v['f1'] * v['support'] for v in per_class.values()) / n
                   if n else 0.0)

    return {
        'accuracy': round(accuracy, 3),
        'macro_f1': round(macro_f1, 3),
        'weighted_f1': round(weighted_f1, 3),
        'per_class': per_class,
    }


def compute_routing_metrics(y_true, y_pred):
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
    }


# ============================================================
# BASELINE 1: TRIVIAL
# ============================================================

def trivial_baseline(messages, human_intents, human_routings):
    """Always predict the single most common intent and routing decision."""
    most_common_intent = Counter(human_intents).most_common(1)[0][0]
    most_common_routing = Counter(human_routings).most_common(1)[0][0]

    pred_intents = [most_common_intent] * len(messages)
    pred_routings = [most_common_routing] * len(messages)

    return pred_intents, pred_routings, {
        'predicted_intent_always': most_common_intent,
        'predicted_routing_always': most_common_routing,
    }


# ============================================================
# BASELINE 2: SIMPLE (keyword-based, no LLM)
# ============================================================

SAFETY_KEYWORDS = [
    'kill myself', 'suicide', 'suicidal', 'want to die', 'harm myself',
    'fuck off', 'fucking idiot', 'stupid bitch', 'harass', 'stalk', 'threaten',
]

NON_ENGLISH_HINTS = [
    r'[\u0400-\u04FF]', r'[\u0600-\u06FF]', r'[\u0900-\u097F]',
    r'[\u4E00-\u9FFF]', r'\b(hola|gracias|bonjour|merci|obrigado|não|está)\b',
]


def simple_keyword_classify(text: str) -> str:
    """Basic keyword-based intent classifier - no LLM, no embeddings."""
    t = text.lower()

    # Priority order: delivery first, then product, then refund, etc.
    if any(kw in t for kw in ['where is', 'when will', 'tracking', 'delivered',
                                'still waiting', 'not arrived', 'not delivered',
                                'shipment', 'out for delivery', 'delivery attempt']):
        return 'delivery_status_inquiry'
    if any(kw in t for kw in ['refund', 'return', 'money back', 'cancel order',
                                'send back']):
        return 'refund_return_request'
    if any(kw in t for kw in ['wrong item', 'damaged', 'broken', 'defective',
                                'not working', 'crashing', 'missing item']):
        return 'order_issue'
    if any(kw in t for kw in ['charge', 'charged', 'billing', 'payment',
                                'unauthorized', 'credit card']):
        return 'payment_billing_issue'
    if any(kw in t for kw in ['password', 'login', 'log in', 'sign in',
                                'account locked', "can't access"]):
        return 'account_access_issue'
    if 'prime' in t and any(kw in t for kw in ['membership', 'subscription',
                                                  'trial', 'cancel prime']):
        return 'prime_membership_inquiry'
    if any(kw in t for kw in ['pathetic', 'terrible', 'worst', 'useless',
                                'disgusting']) and len(t.split()) < 8:
        return 'complaint_no_action'

    return 'general_inquiry'


def simple_is_non_english(text: str) -> bool:
    for pattern in NON_ENGLISH_HINTS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def simple_has_safety_issue(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in SAFETY_KEYWORDS)


def simple_baseline(messages):
    """
    Keyword-based intent + rule-based routing.
    No LLM, no embeddings, no retrieval - a basic rule engine.
    """
    pred_intents = []
    pred_routings = []

    # Intents considered "safe enough" to auto-handle if keyword-matched
    auto_handle_safe_intents = {
        'delivery_status_inquiry', 'general_inquiry', 'prime_membership_inquiry',
    }

    for text in messages:
        intent = simple_keyword_classify(text)
        pred_intents.append(intent)

        # Routing rules
        if simple_has_safety_issue(text):
            routing = 'escalate'
        elif simple_is_non_english(text):
            routing = 'escalate'
        elif intent in ('complaint_no_action', 'payment_billing_issue',
                         'refund_return_request', 'order_issue',
                         'account_access_issue'):
            routing = 'escalate'
        elif intent in auto_handle_safe_intents:
            routing = 'auto_handle'
        else:
            routing = 'escalate'

        pred_routings.append(routing)

    return pred_intents, pred_routings


def main():
    labeled_path = Path('golden_set/labeled.jsonl')
    output_path = Path('outputs/baseline_results.json')

    print("Loading labeled golden set...")
    labeled = load_labeled_set(labeled_path)
    print(f"Loaded {len(labeled)} labeled examples\n")

    messages = []
    human_intents = []
    human_routings = []

    for thread in labeled:
        msg = get_customer_message(thread)
        label = thread.get('label', {})
        if not msg or not label:
            continue
        messages.append(msg)
        human_intents.append(label.get('intent'))
        human_routings.append(label.get('routing'))

    print(f"Using {len(messages)} examples with valid messages and labels\n")
    all_intents = sorted(set(human_intents))

    # --- Baseline 1: Trivial ---
    print("=" * 80)
    print("BASELINE 1: TRIVIAL (majority class)")
    print("=" * 80)
    trivial_intents, trivial_routings, trivial_info = trivial_baseline(
        messages, human_intents, human_routings
    )
    print(f"Always predicts intent: {trivial_info['predicted_intent_always']}")
    print(f"Always predicts routing: {trivial_info['predicted_routing_always']}\n")

    trivial_intent_metrics = compute_classification_metrics(
        human_intents, trivial_intents, all_intents
    )
    trivial_routing_metrics = compute_routing_metrics(human_routings, trivial_routings)

    print(f"Intent accuracy: {trivial_intent_metrics['accuracy']}")
    print(f"Intent macro F1: {trivial_intent_metrics['macro_f1']}")
    print(f"Intent weighted F1: {trivial_intent_metrics['weighted_f1']}")
    print(f"Routing accuracy: {trivial_routing_metrics['accuracy']}")
    print(f"Routing auto-handle precision: {trivial_routing_metrics['auto_handle_precision']}")
    print(f"Routing auto-handle recall: {trivial_routing_metrics['auto_handle_recall']}\n")

    # --- Baseline 2: Simple (keyword-based) ---
    print("=" * 80)
    print("BASELINE 2: SIMPLE (keyword-based rules, no LLM)")
    print("=" * 80)
    simple_intents, simple_routings = simple_baseline(messages)

    simple_intent_metrics = compute_classification_metrics(
        human_intents, simple_intents, all_intents
    )
    simple_routing_metrics = compute_routing_metrics(human_routings, simple_routings)

    print(f"Intent accuracy: {simple_intent_metrics['accuracy']}")
    print(f"Intent macro F1: {simple_intent_metrics['macro_f1']}")
    print(f"Intent weighted F1: {simple_intent_metrics['weighted_f1']}")
    print(f"Routing accuracy: {simple_routing_metrics['accuracy']}")
    print(f"Routing auto-handle precision: {simple_routing_metrics['auto_handle_precision']}")
    print(f"Routing auto-handle recall: {simple_routing_metrics['auto_handle_recall']}\n")

    # --- Save everything ---
    output_data = {
        'n_examples': len(messages),
        'trivial_baseline': {
            'description': trivial_info,
            'intent_metrics': trivial_intent_metrics,
            'routing_metrics': trivial_routing_metrics,
        },
        'simple_baseline': {
            'description': 'Keyword-based intent classifier + rule-based routing, no LLM',
            'intent_metrics': simple_intent_metrics,
            'routing_metrics': simple_routing_metrics,
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2)

    print(f"✓ Full baseline results saved to {output_path}")
    print("\n" + "=" * 80)
    print("COMPARISON SUMMARY (fill in your real system's numbers from eval_results.json)")
    print("=" * 80)
    print(f"{'System':<20} {'Intent Acc':<12} {'Intent F1':<12} {'Routing Acc':<12}")
    print(f"{'Trivial':<20} {trivial_intent_metrics['accuracy']:<12} "
          f"{trivial_intent_metrics['macro_f1']:<12} {trivial_routing_metrics['accuracy']:<12}")
    print(f"{'Simple (keyword)':<20} {simple_intent_metrics['accuracy']:<12} "
          f"{simple_intent_metrics['macro_f1']:<12} {simple_routing_metrics['accuracy']:<12}")
    print(f"{'Your real system':<20} {'(see eval_results.json)':<12}")


if __name__ == "__main__":
    main()
