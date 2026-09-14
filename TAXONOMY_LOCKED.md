# Taxonomy Locked - Moving to Golden Set

## Decision Made

**Taxonomy is LOCKED** as final. No more keyword classifier iterations.

## Critical Design Decision Preserved

**Venting + Topic Routes to Topic Intent**

**The Issue**: Keyword classifier was dumping "angry delivery complaints" into `complaint_no_action`, which would systematically mis-escalate them.

**Example**: "Jesus, I ordered books weeks ago... still don't have!" 
- **Wrong**: `complaint_no_action` → auto-escalate (no topic identified)
- **Right**: `delivery_status_inquiry` → handle delivery complaint

**The Rule**: 
- **Venting + identifiable topic** (delivery/order/refund/etc.) → route to THAT topic's intent
- **Venting with NO topic** ("Pathetic services!!!", "NOTHING YET. WOW") → `complaint_no_action`

**Why it matters**: `complaint_no_action` is defined as strong escalation signal. Mis-routing frustrated-but-actionable requests would create false escalations.

**Preserved in**: `golden_set/approved_taxonomy.json` under `complaint_no_action.design_decision`

---

## Final 8-Intent Taxonomy

| Intent | Description | Natural % | Golden Set % | Notes |
|--------|-------------|-----------|--------------|-------|
| delivery_status_inquiry | Location/timing questions + frustrated follow-ups | ~35-40% | ~35-40% | Includes venting about delays |
| order_issue | Wrong/damaged/missing product | ~10-15% | ~10-15% | NOT Prime service complaints |
| refund_return_request | Explicit refund/return ask | ~8-12% | ~8-12% | Must say "refund"/"return" |
| payment_billing_issue | Charges, unauthorized transactions | ~5-8% | ~5-8% | |
| account_access_issue | Login, password, locked account | ~1-3% | **~5-10%** | **Oversampled** for evaluation |
| prime_membership_inquiry | Prime subscription/benefits | ~2-4% | **~5-10%** | **Oversampled** |
| general_inquiry | Miscellaneous questions with clear ask | ~10-20% | ~10-20% | NOT topic + venting |
| complaint_no_action | TOPIC-LESS venting only | ~1-2% | **~5-10%** | **Oversampled** |

**Total**: 200 threads for golden set (target)

---

## What Was Thrown Away

**Keyword classification logic** in `06_refine_taxonomy.py`:
- ❌ All the keyword rules
- ❌ The pain of perfecting them for edge cases
- ❌ The 44.7% complaint_no_action bug
- ❌ The inability to handle French/non-English

**Why**: Keyword rules were for taxonomy bootstrapping only. Real classifier is LLM-based.

---

## What Was Kept

**From taxonomy derivation**:
- ✅ 8 intent categories (correct)
- ✅ Written descriptions and disambiguation rules
- ✅ Example utterances per intent
- ✅ Design decisions (venting+topic rule)

**Going forward**:
- ✅ Approved taxonomy JSON (`golden_set/approved_taxonomy.json`)
- ✅ Language filter (`src/language_filter.py`)
- ✅ Safety filter (`src/safety_filters.py`)

---

## Files Created

**Locked taxonomy**:
- `golden_set/approved_taxonomy.json` — Source of truth for intents
  - 8 intents with descriptions
  - Disambiguation rules
  - Example utterances
  - Design decisions documented
  - Oversampling strategy specified

**Golden set sampling**:
- `scripts/07_sample_golden_set.py` — Sample 200 threads from full ~82k AmazonHelp data
  - Stratified by intent
  - Oversamples rare intents
  - Applies language filter (English-only)
  - Applies safety filter (flags crisis/PII)
  - Ready for hand-labeling

---

## Next Steps

### 1. Run Golden Set Sampling

```bash
python scripts\07_sample_golden_set.py --size 200
```

**Outputs**:
- `golden_set/unlabeled_sample.jsonl` — 200 threads
- `golden_set/filter_stats.json` — Language/safety stats

**Expected**:
- ~35-40% delivery status
- ~5-10% each of rare intents (oversampled)
- English-only (non-English filtered)
- Safety flags preserved (not excluded)

### 2. Hand-Label Golden Set

**YOU will**:
- Review all 200 threads
- Assign correct intent (one of 8)
- Assign routing decision (auto-handle vs. escalate)
- Note escalation reason if escalated

**Format**: Add to each thread JSON:
```json
{
  "thread_id": "...",
  "messages": [...],
  "label": {
    "intent": "delivery_status_inquiry",
    "routing": "escalate",
    "routing_reason": "Delivery confirmed but customer claims non-receipt",
    "labeler_confidence": "high",
    "labeler_notes": ""
  }
}
```

**Save as**: `golden_set/labeled.jsonl`

### 3. Build LLM Classifier

**Next script** (`scripts/08_build_llm_classifier.py`):
- Loads `approved_taxonomy.json`
- Builds few-shot Gemini prompt
- Classifies using Gemini Flash (free tier)
- Caches responses (input hash → classification)
- Rate limits (15 req/min)

### 4. Evaluate

**Run classifier on golden set**:
- Intent classification: Accuracy, per-class F1, macro F1
- Routing decision: Precision/recall (auto-handle as positive class)
- Confusion matrix analysis

**Compare to baselines**:
- Trivial: Majority class + canned reply
- Simple: Keyword rules + non-RAG LLM

---

## Timeline Estimate

| Phase | Time | Who |
|-------|------|-----|
| Run sampling script | ~5 min | Script |
| Review sample | ~30 min | You |
| Hand-label 200 threads | **~2-3 hours** | **YOU** |
| Build LLM classifier | ~1 hour | Script + you |
| Run evaluation | ~30 min | Script |
| Failure analysis | ~1-2 hours | You |
| Report writing | ~3-4 hours | You |

**Total remaining**: ~8-12 hours of work

---

## Success Criteria

**Taxonomy is good enough if**:
- ✅ 8 intents are distinct and cover AmazonHelp issues
- ✅ Disambiguation rules are clear
- ✅ Design decisions documented (venting+topic)
- ✅ Can hand-label golden set consistently

**You've achieved this**. The keyword classifier's imperfections don't matter because:
1. It was for bootstrapping only
2. LLM classifier will handle edge cases
3. Golden set hand-labeling fixes any misclassifications
4. Evaluation rigor is the actual deliverable

---

## Ready to Proceed?

**Command to run**:
```bash
python scripts\07_sample_golden_set.py --size 200
```

**This will**:
- Filter ~82k AmazonHelp threads
- Apply language filter (English-only, report stats)
- Apply safety filter (flag but don't exclude)
- Stratified sample 200 threads
- Oversample rare intents
- Output `golden_set/unlabeled_sample.jsonl`

**Then you label**, and we move to LLM classifier + evaluation.

---

**Taxonomy is locked. Moving forward.**
