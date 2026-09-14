# Pipeline Implementation Status

## ✅ COMPLETE: Classifier + RAG + Routing Scaffolding

### What's Built

**4 core components**:

1. **Intent Classifier** (`src/intent_classifier.py`)
   - Gemini Flash few-shot from approved_taxonomy.json
   - Response caching (hash-keyed)
   - Rate limiting (15 req/min free tier)
   - Output: intent + confidence + reasoning

2. **RAG Retriever** (`src/rag_retriever.py`)
   - sentence-transformers (all-MiniLM-L6-v2, local, free)
   - FAISS similarity search
   - **CRITICAL**: Explicit golden-set exclusion with hard assertion
   - Caches: corpus, embeddings, retrieval results

3. **Reply Drafter** (`src/reply_drafter.py`)
   - Groq Llama 3.1 8B Instant (free tier)
   - Grounded in retrieved historical resolutions
   - Response caching
   - Output: drafted_reply + grounding_strength

4. **Router** (`src/router.py`)
   - Safety filter (crisis/PII/abuse/threat) → mandatory escalate
   - Language filter (non-English) → mandatory escalate
   - Intent + confidence + grounding logic
   - "When in doubt, escalate" bias
   - Output: routing + routing_reason + flags

**End-to-end pipeline** (`scripts/run_pipeline.py`):
- Takes customer message → returns full result
- Single message or batch processing
- Caching throughout
- `--build-corpus` for first-time setup
- `--test` for sanity checking

---

## Golden Set Exclusion (Zero Leakage)

**Implementation**:
```python
# Load golden set IDs
golden_set_ids = {thread['thread_id'] for thread in golden_set}

# Build corpus (skip golden set)
for thread in all_threads:
    if thread['thread_id'] in golden_set_ids:
        continue  # EXCLUDED
    corpus.append(...)

# HARD ASSERTION
corpus_ids = {entry['thread_id'] for entry in corpus}
leaked_ids = corpus_ids.intersection(golden_set_ids)
if leaked_ids:
    raise AssertionError(f"GOLDEN SET LEAKAGE: {len(leaked_ids)} threads!")
```

**Result**: No golden-set thread can appear in RAG corpus. Fails loudly if violated.

---

## Routing Logic (Matches Hand-Labeling Bias)

**Priority order**:
1. Safety flag → `escalate` (mandatory)
2. Language flag → `escalate` (mandatory)
3. Escalate-prone intents (`complaint_no_action`, `payment_billing_issue`) → `escalate`
4. Low confidence → `escalate`
5. Medium confidence + weak grounding → `escalate`
6. High confidence + safe intent + strong grounding → `auto_handle`
7. Default → `escalate` (when in doubt)

**Thresholds**:
- Confidence: Only `high` for auto-handle
- Grounding: ≥0.6 similarity required
- Safe intents: `delivery_status_inquiry`, `general_inquiry`, `account_access_issue`

**Documented** in `src/router.py` with explicit logic, not implicit heuristics.

---

## Sanity Testing

**Test file**: `test_messages.txt` (8 sample messages)

**Run**:
```bash
# First time: build corpus (~10-15 min)
python scripts\run_pipeline.py --build-corpus

# Test single message
python scripts\run_pipeline.py --test "Where is my package?"

# Test all samples
python scripts\run_pipeline.py --test-file test_messages.txt --output results.json
```

**Expected**:
- Delivery status → auto_handle (high conf + strong grounding)
- Wrong item → escalate (order_issue default)
- Refund → escalate (financial risk)
- Venting → escalate (complaint_no_action)
- Safety keyword → escalate (safety flagged)
- Non-English → escalate (language flagged)

---

## API Keys Required

**`.env` file**:
```bash
GOOGLE_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_key
```

**Get keys**:
- Gemini: https://aistudio.google.com/app/apikey (free tier: 15 req/min)
- Groq: https://console.groq.com/keys (free tier: fast, generous)

---

## Caching Strategy

**All responses cached** to preserve free-tier quotas:

- Intent classifications: `cache/pipeline/classifier_cache/<hash>.json`
- Retrieval results: `cache/pipeline/rag_cache/retrieval_<hash>.json`
- Drafted replies: `cache/pipeline/drafter_cache/<hash>.json`
- RAG corpus/embeddings: `cache/pipeline/rag_cache/` (pkl, npy, faiss.index)

**Result**: Re-running on same inputs = instant, zero API calls.

---

## What's NOT Built Yet

**Evaluation harness** (next step):
- Run classifier on 197 hand-labeled golden set
- Compute accuracy, per-class F1, confusion matrix
- Routing precision/recall (system vs human labels)
- Compare to baselines (majority class, keyword rules)

**Failure analysis**:
- Top 5 failure modes with examples
- Intent confusion patterns
- Routing disagreement cases

**Report generation**:
- Problem framing
- Results vs baselines
- "What's misleading" section
- Decision log

---

## Files Created

**Source code**:
- `src/intent_classifier.py` (293 lines)
- `src/rag_retriever.py` (244 lines)
- `src/reply_drafter.py` (183 lines)
- `src/router.py` (147 lines)
- `scripts/run_pipeline.py` (350 lines)

**Documentation**:
- `PIPELINE_GUIDE.md` (comprehensive usage guide)
- `PIPELINE_STATUS.md` (this file)

**Test data**:
- `test_messages.txt` (8 sample messages)

---

## Next Action

**User**: Run sanity tests to confirm pipeline works on manual examples.

**Commands**:
```bash
# 1. Build RAG corpus (first time only, ~10-15 min)
python scripts\run_pipeline.py --build-corpus

# 2. Test single message
python scripts\run_pipeline.py --test "Where is my package?"

# 3. Test all samples
python scripts\run_pipeline.py --test-file test_messages.txt --output results.json

# 4. Review results.json - check intent, routing, grounding
```

**After sanity check passes**: Build evaluation harness to measure accuracy on golden set.

---

**Status**: Ready for sanity testing. No evaluation yet.
