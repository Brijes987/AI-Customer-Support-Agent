# Golden Set Labeling Guide

## Quick Start

```bash
python scripts\label_golden_set.py
```

**Press Enter to begin**, then for each conversation:
1. Read the messages
2. Type `1-8` to select intent
3. Type `1` (auto) or `2` (escalate)
4. Type one-line reason
5. Type `1-3` for confidence (or Enter for high)

**Saves automatically** after each label. Safe to stop anytime (Ctrl+C or type `q`).

**Resume later**:
```bash
python scripts\label_golden_set.py --resume
```

---

## Display Format

Each thread shows:
```
THREAD 1 of 197
================================================================================

⚠️  ⚠️  ⚠️  SAFETY FLAGGED ⚠️  ⚠️  ⚠️     ← If triggered safety filter
Reasons: Crisis keyword detected: 'kill myself'
This thread likely requires ESCALATION
================================================================================

Suggested intent (from sampling): delivery_status_inquiry  ← Hint, not truth

[1] CUSTOMER (@username):
    Where is my package? Order #12345

[2] BRAND (@AmazonHelp):
    Hi! Let me check that for you...
```

---

## Intent Selection

```
Select INTENT (1-8):
  1. delivery_status_inquiry
     Customer asking about delivery status, tracking, or when...
  2. order_issue
     Problem with the product itself: wrong item received,...
  3. refund_return_request
     Customer explicitly requesting refund, return, or order...
  4. payment_billing_issue
     Issues with charges, payment methods, unauthorized...
  5. account_access_issue
     Login problems, password resets, account locked, or...
  6. prime_membership_inquiry
     Questions about Prime membership, subscription, benefits...
  7. general_inquiry
     General questions or requests that don't fit other...
  8. complaint_no_action
     Pure frustration/venting with NO identifiable subject...

Your choice (1-8, or 'q' to save and quit): 
```

**Type**: Number 1-8, or `q` to quit

---

## Routing Decision

```
Routing decision:
  1. Auto-handle (safe to handle automatically)
  2. Escalate (send to human agent)

Your choice (1 or 2): 
```

**Guidelines**:
- **Auto-handle (1)**: Straightforward request, clear resolution path, low risk
- **Escalate (2)**: 
  - Safety-flagged (crisis/abuse/PII)
  - High-value dispute
  - Complex policy question
  - Customer claims delivery but tracking shows delivered
  - Unclear what customer wants

**When in doubt**: Escalate. Better safe than wrong.

---

## Routing Reason

```
Reason (one line):
> Standard delivery status inquiry
```

**Examples**:
- Auto-handle: `"Standard delivery status inquiry"`, `"Simple refund within policy"`, `"Password reset request"`
- Escalate: `"Safety flagged: crisis keyword"`, `"Delivered but customer claims non-receipt"`, `"High-value item dispute"`, `"Unclear request, needs clarification"`

**Can be brief** — you're not writing a novel.

---

## Confidence

```
Your confidence in this label:
  1. High (very clear)
  2. Medium (reasonable judgment)
  3. Low (uncertain/ambiguous)

Confidence (1-3, or press Enter for High): 
```

**Just press Enter** for most cases (defaults to High).

Use Medium/Low for:
- Borderline between two intents
- Unclear what customer wants
- Venting that might be topic-less or topic-specific

---

## Ambiguous Cases - Decision Rules

### "Angry about delivery" — delivery_status_inquiry or complaint_no_action?
**Answer**: `delivery_status_inquiry`

**Rule**: Venting + topic routes to topic intent. Only pure topic-less venting ("NOTHING YET. WOW") goes to complaint_no_action.

---

### "Wrong item, want refund" — order_issue or refund_return_request?
**Answer**: `refund_return_request` if they explicitly say "refund"

**Rule**: Explicit refund ask = refund_return_request. Complaint about wrong item without refund ask = order_issue.

---

### "Not getting prime service" — prime_membership_inquiry?
**Answer**: NO. `delivery_status_inquiry` or `general_inquiry`

**Rule**: Prime intent is for subscription/membership questions only. Service complaints are NOT Prime intent.

---

### French/non-English message in sample?
**Answer**: Skip or label as best you can, note in confidence=low

**Should be filtered** (language filter may have missed it). If you see many, note count for report.

---

## Progress Tracking

**Auto-saves after every label** to `golden_set/labeled.jsonl`.

**See progress**:
```
✓ Saved label 50/197
   147 threads remaining
```

**Stop anytime**:
- Press Ctrl+C
- Type `q` when choosing intent
- Close terminal (safe — progress saved)

**Resume later**:
```bash
python scripts\label_golden_set.py --resume
```

Picks up where you left off.

---

## Output Format

**File**: `golden_set/labeled.jsonl`

**Format** (each line is one thread):
```json
{
  "thread_id": "123456789",
  "messages": [...],
  "sampling_metadata": {...},
  "label": {
    "intent": "delivery_status_inquiry",
    "routing": "auto_handle",
    "routing_reason": "Standard delivery status inquiry",
    "labeler_confidence": "high",
    "labeled_at": "2026-09-09T15:30:00"
  }
}
```

**Used by**: Evaluation scripts, classifier training (if needed), failure analysis.

---

## Tips for Speed

1. **Trust your gut** — first instinct is usually right
2. **Press Enter** for confidence (defaults to High)
3. **Brief reasons** — "Standard case" is fine for auto-handle
4. **Use suggested intent** as starting point (but override if wrong)
5. **Don't overthink** — ambiguous cases happen, pick most reasonable
6. **Take breaks** — saves automatically, resume anytime

**Target pace**: ~1-2 minutes per thread → 3-6 hours total for 197 threads

---

## Troubleshooting

**"No such file: unlabeled_sample.jsonl"**
→ Run golden set sampling first: `python scripts\07_sample_golden_set.py --size 200`

**"approved_taxonomy.json not found"**
→ Warning only. Uses default 8 intents. Should not affect labeling.

**Non-English text appears**
→ Language filter missed it. Label as best you can or skip (note in report).

**Safety-flagged thread seems fine**
→ Filter might be overly cautious (e.g., mentions "kill" in "kill time"). Use your judgment. If genuinely concerning, escalate.

**Want to change a previous label**
→ Edit `labeled.jsonl` directly (it's line-by-line JSON), or delete the line and re-run with `--resume`.

---

## After Labeling Complete

```bash
✓ All threads labeled!

NEXT STEPS:
  1. Review labeled.jsonl for consistency
  2. Build LLM classifier (scripts/08_build_llm_classifier.py)
  3. Evaluate classifier on labeled golden set
```

---

**Ready to label? Just run:**
```bash
python scripts\label_golden_set.py
```

**Estimated time**: 3-6 hours (with breaks). You can split across multiple sessions.
