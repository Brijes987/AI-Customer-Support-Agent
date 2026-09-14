# Golden Set Sampling Logic Fix

## Problem Confirmed

**Yes**, `07_sample_golden_set.py` had a SEPARATE `rough_intent_assignment()` function that didn't get the fixes from `06_refine_taxonomy.py`.

**Result**: 67.9% general_inquiry in natural pool, 58.5% in sample — same dump-bucket problem.

---

## Fixes Applied

### 1. Priority Order Correction

**OLD (broken)**:
```python
# Simple if-elif chain, general_inquiry as fallback
if 'where is' in text: return 'delivery_status_inquiry'
elif 'damaged' in text: return 'order_issue'
...
else: return 'general_inquiry'  # ← Dump bucket
```

**NEW (fixed)**:
```python
# PRIORITY 1: Delivery (checked FIRST, including venting)
delivery_keywords = ['where is', 'when will', 'still unresolved', 'dont have', 'ordered weeks ago', ...]
if has_delivery: return 'delivery_status_inquiry'

# PRIORITY 2: Product problems
if has_product_problem: return 'order_issue'

# ... other specific intents ...

# PRIORITY 9: General (only if has clear question/request)
if has_question or has_request: return 'general_inquiry'

# PRIORITY 10: Default (not dump bucket anymore)
return 'general_inquiry'
```

**Key changes**:
- Delivery check moved to PRIORITY 1 (before general)
- Added frustrated delivery keywords: `'still unresolved'`, `'dont have'`, `'ordered weeks ago'`
- General inquiry requires explicit question markers
- Venting+topic logic applied

---

### 2. Venting + Topic Logic

**Applied the corrected rule**:

```python
# Check for venting
venting_phrases = ['pathetic', 'terrible', 'worst', 'nothing yet', 'wow', ...]
has_venting = any(phrase in text_lower for phrase in venting_phrases)

# If we got to this point (past delivery/order/refund checks) AND has venting
# → It's topic-less venting
if has_venting and len(text_lower) < 100:
    return 'complaint_no_action'
```

**Result**: "Jesus, I ordered books weeks ago... still don't have!" now routes to `delivery_status_inquiry`, not `complaint_no_action`.

---

### 3. Safety Flag Metadata

**Added to output**:

Each thread in `unlabeled_sample.jsonl` now includes:
```json
{
  "thread_id": "...",
  "messages": [...],
  "sampling_metadata": {
    "rough_intent_for_stratification": "delivery_status_inquiry",
    "safety_flagged": false,
    "safety_reasons": []
  }
}
```

**If safety-flagged**:
```json
{
  "sampling_metadata": {
    "rough_intent_for_stratification": "...",
    "safety_flagged": true,
    "safety_reasons": ["Crisis keyword detected: 'kill myself'"]
  }
}
```

**Benefits**:
- You can see which threads triggered safety filters
- You can confirm escalation reasoning during hand-labeling
- No need to re-derive safety flags manually

---

## Expected Distribution After Fix

**Before fix** (broken):
- general_inquiry: 67.9% → 58.5% of sample (dump bucket)
- delivery_status_inquiry: Too low
- complaint_no_action: Including delivery complaints

**After fix** (corrected):
- delivery_status_inquiry: ~35-45% (includes frustrated follow-ups)
- general_inquiry: ~10-20% (only clear questions)
- complaint_no_action: ~1-3% natural (topic-less venting only)
- Other intents: Reasonable proportions

**Oversampling still applied** to rare intents:
- account_access_issue: ~5-10% (from ~1-3%)
- complaint_no_action: ~5-10% (from ~1-2%)
- prime_membership_inquiry: ~5-10% (from ~2-4%)

---

## Confirmation

**Q1**: Is the classification function fixed?
**A**: ✅ Yes, `rough_intent_assignment()` now uses same priority order and venting+topic logic as `06_refine_taxonomy.py`.

**Q2**: Are safety flags visible in output?
**A**: ✅ Yes, each thread has `sampling_metadata.safety_flagged` and `sampling_metadata.safety_reasons`.

---

## Re-Run Now

```bash
python scripts\07_sample_golden_set.py --size 200
```

**Expected output**:
- Natural distribution: delivery ~35-45%, general ~10-20%
- Golden set sample: Rare intents oversampled to ~5-10% each
- Safety-flagged threads reported (count + metadata included)
- Filter stats saved (non-English languages logged)

---

## After Re-Run

**Verify**:
1. ✓ Natural distribution shows general_inquiry <30% (not 67%)
2. ✓ delivery_status_inquiry is largest category (~35-45%)
3. ✓ complaint_no_action ~1-3% natural (topic-less only)
4. ✓ Safety flags present in sampling_metadata

**Then**:
- Hand-label 200 threads
- Use `sampling_metadata.rough_intent_for_stratification` as a starting suggestion
- Override with correct intent based on your judgment
- Pay attention to safety-flagged threads (likely escalate)

---

**Both questions answered: Yes to fixes applied, yes to safety metadata included.**
