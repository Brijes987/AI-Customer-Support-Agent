#!/usr/bin/env python3
"""
Stage 10: LLM-as-judge for reply quality.

Scores each drafted reply (from outputs/eval_results.json) on a 4-dimension
rubric using Gemini as the judge - a DIFFERENT model/role than the one that
drafted the replies (Groq), to reduce self-grading bias.

Also produces a human-scoring template: a subset of examples for YOU to
score by hand, so judge-human agreement can be measured honestly.

Usage:
    python scripts/10_llm_judge.py --limit 20
    python scripts/10_llm_judge.py --human-sample 15   # generate human scoring template
    python scripts/10_llm_judge.py --compare-agreement # compare your scores vs judge
"""

import argparse
import json
import time
import os
from pathlib import Path

from dotenv import load_dotenv
import google.generativeai as genai

RUBRIC_PROMPT = """You are an impartial quality judge for customer support replies. \
Score the DRAFTED REPLY below on 4 dimensions, each from 1 (poor) to 5 (excellent).

# Customer Message
"{customer_message}"

# Intent (predicted)
{intent}

# Historical Context Used for Grounding
{grounding_context}

# Drafted Reply to Judge
"{drafted_reply}"

# Rubric Dimensions

1. CORRECTNESS/GROUNDEDNESS (1-5): Does the reply make claims that are actually \
supported by the grounding context or general policy knowledge? Does it invent \
specific facts (order numbers, dates, promises) that weren't actually given? \
Hallucinated specifics should score LOW even if the reply sounds confident.

2. TONE (1-5): Is the tone appropriately empathetic and professional for the \
customer's emotional state, without being robotic or excessively apologetic?

3. COMPLETENESS (1-5): Does the reply actually address the customer's specific \
question or concern, or does it give a generic non-answer?

4. ACTIONABILITY (1-5): Does the reply give the customer a clear next step \
(a link, a question to answer, information they can act on), or does it leave \
them without any path forward?

Return ONLY valid JSON in this exact format:
{{"correctness": <1-5>, "tone": <1-5>, "completeness": <1-5>, "actionability": <1-5>, "brief_reasoning": "<one sentence>"}}
"""


def load_eval_results(path: Path):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data['raw_results']


def judge_reply(model, entry, retry_delay=2.0):
    """Call Gemini to score one drafted reply against the rubric."""
    grounding_context = "No strong historical match was found." if entry.get('grounding_strength', 0) < 0.3 else \
        "A similar historical case was retrieved (see similarity score)."

    prompt = RUBRIC_PROMPT.format(
        customer_message=entry['customer_message'][:500],
        intent=entry['predicted_intent'],
        grounding_context=grounding_context,
        drafted_reply=entry['drafted_reply'],
    )

    for attempt in range(4):
        try:
            response = model.generate_content(prompt)
            text = response.text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            result = json.loads(text)
            return result
        except Exception as e:
            if attempt == 3:
                return {
                    'correctness': None, 'tone': None, 'completeness': None,
                    'actionability': None, 'brief_reasoning': f'JUDGE ERROR: {e}',
                }
            time.sleep(retry_delay * (attempt + 1))


def run_judge(args):
    load_dotenv()
    api_key = os.getenv('GOOGLE_API_KEY')
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-flash-lite-latest')

    eval_path = Path('outputs/eval_results.json')
    output_path = Path('outputs/judge_results.json')

    print("Loading evaluation results...")
    entries = load_eval_results(eval_path)
    if args.limit:
        entries = entries[:args.limit]
    print(f"Judging {len(entries)} drafted replies...\n")

    judged = []
    for i, entry in enumerate(entries, 1):
        print(f"[{i}/{len(entries)}] Judging: {entry['customer_message'][:60]!r}")
        scores = judge_reply(model, entry)
        judged.append({
            'thread_id': entry.get('thread_id'),
            'customer_message': entry['customer_message'],
            'drafted_reply': entry['drafted_reply'],
            'predicted_intent': entry['predicted_intent'],
            'human_intent': entry.get('human_intent'),
            'judge_scores': scores,
        })
        if scores['correctness'] is not None:
            avg = (scores['correctness'] + scores['tone'] +
                   scores['completeness'] + scores['actionability']) / 4
            print(f"  Scores: correctness={scores['correctness']} tone={scores['tone']} "
                  f"completeness={scores['completeness']} actionability={scores['actionability']} "
                  f"(avg={avg:.2f})")
        else:
            print(f"  ERROR: {scores['brief_reasoning']}")
        time.sleep(0.3)

    # Aggregate stats
    valid = [j['judge_scores'] for j in judged if j['judge_scores']['correctness'] is not None]
    if valid:
        avg_correctness = sum(s['correctness'] for s in valid) / len(valid)
        avg_tone = sum(s['tone'] for s in valid) / len(valid)
        avg_completeness = sum(s['completeness'] for s in valid) / len(valid)
        avg_actionability = sum(s['actionability'] for s in valid) / len(valid)
        overall_avg = (avg_correctness + avg_tone + avg_completeness + avg_actionability) / 4

        print(f"\n{'=' * 80}")
        print(f"AGGREGATE JUDGE SCORES (n={len(valid)})")
        print('=' * 80)
        print(f"Correctness/Groundedness: {avg_correctness:.2f}/5")
        print(f"Tone: {avg_tone:.2f}/5")
        print(f"Completeness: {avg_completeness:.2f}/5")
        print(f"Actionability: {avg_actionability:.2f}/5")
        print(f"Overall average: {overall_avg:.2f}/5")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(judged, f, indent=2)
    print(f"\n✓ Full judge results saved to {output_path}")


def generate_human_sample(args):
    """Pick a random subset of judged examples for the user to score by hand."""
    import random

    judge_path = Path('outputs/judge_results.json')
    output_path = Path('outputs/human_scoring_template.json')

    with open(judge_path, 'r', encoding='utf-8') as f:
        judged = json.load(f)

    valid = [j for j in judged if j['judge_scores']['correctness'] is not None]
    n = min(args.human_sample, len(valid))
    sample = random.sample(valid, n)

    template = []
    for entry in sample:
        template.append({
            'thread_id': entry['thread_id'],
            'customer_message': entry['customer_message'],
            'drafted_reply': entry['drafted_reply'],
            'judge_scores': entry['judge_scores'],  # kept for later comparison, don't peek while scoring!
            'YOUR_SCORES': {
                'correctness': None,
                'tone': None,
                'completeness': None,
                'actionability': None,
            },
        })

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(template, f, indent=2)

    print(f"✓ Generated human-scoring template with {n} examples: {output_path}")
    print("\nINSTRUCTIONS:")
    print("1. Open outputs/human_scoring_template.json in a text editor")
    print("2. For each example, read customer_message and drafted_reply")
    print("3. Fill in YOUR_SCORES (1-5 for each dimension) based on your own judgment")
    print("4. IMPORTANT: don't look at judge_scores while scoring - score independently first")
    print("5. Once done, run: python scripts/10_llm_judge.py --compare-agreement")


def compare_agreement(args):
    """Compute agreement between human scores and judge scores."""
    path = Path('outputs/human_scoring_template.json')
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    dimensions = ['correctness', 'tone', 'completeness', 'actionability']
    diffs = {d: [] for d in dimensions}
    exact_matches = {d: 0 for d in dimensions}
    n = 0

    for entry in data:
        human = entry['YOUR_SCORES']
        judge = entry['judge_scores']
        if any(human[d] is None for d in dimensions):
            continue
        n += 1
        for d in dimensions:
            diff = abs(human[d] - judge[d])
            diffs[d].append(diff)
            if diff == 0:
                exact_matches[d] += 1

    if n == 0:
        print("No scored examples found. Fill in YOUR_SCORES in human_scoring_template.json first.")
        return

    print(f"Agreement analysis over {n} human-scored examples:\n")
    for d in dimensions:
        mean_abs_diff = sum(diffs[d]) / len(diffs[d])
        exact_pct = exact_matches[d] / n * 100
        within_1 = sum(1 for x in diffs[d] if x <= 1) / n * 100
        print(f"{d.upper()}:")
        print(f"  Mean absolute difference: {mean_abs_diff:.2f} points (on a 1-5 scale)")
        print(f"  Exact match: {exact_pct:.0f}%")
        print(f"  Within 1 point: {within_1:.0f}%\n")


def main():
    parser = argparse.ArgumentParser(description="LLM-as-judge for reply quality")
    parser.add_argument('--limit', type=int, default=None,
                         help='Number of eval_results.json entries to judge')
    parser.add_argument('--human-sample', type=int, default=None,
                         help='Generate a human-scoring template with N random examples')
    parser.add_argument('--compare-agreement', action='store_true',
                         help='Compare your filled-in human scores against judge scores')
    args = parser.parse_args()

    if args.compare_agreement:
        compare_agreement(args)
    elif args.human_sample:
        generate_human_sample(args)
    else:
        run_judge(args)


if __name__ == "__main__":
    main()
