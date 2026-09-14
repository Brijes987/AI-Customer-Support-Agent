# Customer Support AI Pipeline Guide

## Overview

End-to-end system with 4 components:

1. **Intent Classifier** - Gemini Flash few-shot (8 intents from taxonomy)
2. **RAG Retriever** - sentence-transformers + FAISS (local, free)
3. **Reply Drafter** - Groq grounded generation (from retrieved examples)
4. **Router** - Safety + language + logic → auto-handle or escalate

**Zero-cost**: All free-tier APIs. All responses cached to disk.

---

## First-Time Setup

### 1. API Keys

Create `.env` file in project root:

```bash
GOOGLE_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here
```

**Get keys**:
- Gemini: https://aistudio.google.com/app/apikey
- Groq: https://console.groq.com/keys

### 2. Build RAG Corpus

**CRITICAL**: This excludes all 197 golden-set threads from corpus (zero leakage).

```bash
python scripts\run_pipeline.py --build-corpus
```

**What it does**:
1. Loads all AmazonHelp threads from `data/processed/threads.jsonl`
2. Loads golden set thread IDs from `golden_set/unlabeled_sample.jsonl`
3. **Excludes** every golden-set thread from corpus
4. **Asserts** no golden-set thread leaked into corpus (hard failure if violated)
5. Generates embeddings using sentence-transformers (local)
6. Builds FAISS index for fast similarity search
7. Caches everything to `cache/pipeline/rag_cache/`

**Expected output**:
```
✓ Golden set: 197 threads (WILL BE EXCLUDED)
✓ Loaded 82,555 AmazonHelp threads
✓ Built corpus: ~82,358 entries
  Excluded 197 golden-set threads
✓ Assertion passed: No golden-set threads in corpus
✓ Generated embeddings: shape (82358, 384)
✓ FAISS index built: 82358 vectors
```

**Time**: ~10-15 minutes first run. Subsequent runs load from cache (<5 sec).

---

## Usage

### Test Single Message

```bash
python scripts\run_pipeline.py --test "Where is my package?"
```

**Output**:
```
Processing Customer Message
================================================================================

Customer: "Where is my package?"

[1/4] Classifying intent...
✓ Intent: delivery_status_inquiry (confidence: high)
  Reasoning: Clear delivery status question

[2/4] Retrieving top-5 similar cases...
✓ Retrieved 5 examples
  Top similarity: 0.892

[3/4] Drafting reply...
✓ Reply drafted
  Grounding strength: 0.856
  Reply: "Hi! I'd be happy to help track your package. Could you please provide..."

[4/4] Making routing decision...
✓ Routing: AUTO_HANDLE
  Reason: High confidence, safe intent, strong grounding (0.86)
```

### Test Multiple Messages

```bash
python scripts\run_pipeline.py --test-file test_messages.txt --output results.json
```

Processes all messages in file (one per line), saves results to JSON.

### Force Fresh API Calls (No Cache)

```bash
python scripts\run_pipeline.py --test "Where is my package?" --no-cache
```

**Use case**: Testing prompt changes, re-running with different models.

---

## Output Format

Each processed message returns:

```json
{
  "customer_message": "Where is my package?",
  "intent": "delivery_status_inquiry",
  "intent_confidence": "high",
  "intent_reasoning": "Clear delivery status question with tracking request",
  "retrieved_examples": [
    {
      "customer_message": "Where is my order? Still waiting...",
      "brand_resolution": "Hi! I've checked your order #... Expected delivery...",
      "similarity_score": 0.892,
      "thread_id": "123456789"
    }
  ],
  "drafted_reply": "Hi! I'd be happy to help track your package...",
  "grounding_strength": 0.856,
  "routing": "auto_handle",
  "routing_reason": "High confidence, safe intent, strong grounding (0.86)",
  "safety_flagged": false,
  "language_flagged": false
}
```

---

## Component Details

### 1. Intent Classifier (`src/intent_classifier.py`)

**Model**: Gemini Flash 1.5 (free tier: 15 req/min)

**Prompt**: Built from `approved_taxonomy.json`:
- 8 intent definitions with descriptions
- Disambiguation rules (venting+topic, priority order)
- Example utterances per intent
- Critical design decisions (no Prime service complaints in Prime intent, etc.)

**Output**: `{intent, confidence, reasoning}`

**Caching**: Every response saved to `cache/pipeline/classifier_cache/<hash>.json`

**Rate limiting**: 4 sec between requests (conservative for 15/min limit)

**Retry logic**: 3 attempts with exponential backoff

---

### 2. RAG Retriever (`src/rag_retriever.py`)

**Embedding model**: `all-MiniLM-L6-v2` (384-dim, local, fast)

**Index**: FAISS IndexFlatIP (inner product = cosine similarity after normalization)

**Corpus**: ~82,358 AmazonHelp threads (golden set EXCLUDED)

**Retrieval**:
- Embed customer message
- Find top-k most similar historical customer messages
- Return historical resolutions + similarity scores

**Caching**:
- Corpus: `cache/pipeline/rag_cache/corpus.pkl`
- Embeddings: `cache/pipeline/rag_cache/embeddings.npy`
- FAISS index: `cache/pipeline/rag_cache/faiss.index`
- Retrieval results: `cache/pipeline/rag_cache/retrieval_<hash>.json`

**Golden set exclusion**: Hard assertion fails build if any golden-set thread found in corpus.

---

### 3. Reply Drafter (`src/reply_drafter.py`)

**Model**: Groq Llama 3.1 8B Instant (free tier: fast, no strict rate limit published)

**Prompt**:
- Customer message
- Top-k retrieved historical cases (customer message + brand resolution)
- Instructions to ground reply in historical examples

**Output**: `{drafted_reply, grounding_strength, num_examples_used}`

**Grounding strength**: Average similarity of top-3 retrieved examples (0-1)

**Caching**: Every response saved to `cache/pipeline/drafter_cache/<hash>.json`

**Rate limiting**: 0.5 sec between requests (conservative)

---

### 4. Router (`src/router.py`)

**Priority order**:

1. **Safety filter** (mandatory escalation)
   - Crisis keywords: suicide, self-harm
   - Threats: violence, harm to others
   - PII exposure: credit cards, SSNs
   - Abuse: harassment, hate speech

2. **Language filter** (mandatory escalation)
   - Non-English messages → escalate (out of scope)

3. **Intent-based routing**:
   - **Escalate-prone intents**: `complaint_no_action`, `payment_billing_issue`
   - **Low confidence**: Always escalate
   - **Medium confidence + weak grounding**: Escalate
   - **High confidence + safe intent + strong grounding**: Auto-handle
   - **Default**: Escalate (when in doubt)

**Safe intents for auto-handle**:
- `delivery_status_inquiry`
- `general_inquiry`
- `account_access_issue`

**Thresholds** (tunable in `src/router.py`):
- Confidence threshold: `high` (only auto-handle high confidence)
- Grounding threshold: `0.6` (require decent similarity match)

**Output**: `{routing, routing_reason, safety_flagged, language_flagged}`

---

## Caching Strategy

**Why**: Free-tier APIs have rate limits and quotas. Caching preserves quota for evaluation runs.

**What's cached**:
1. Intent classifications (by message hash)
2. Retrieval results (by message + k)
3. Drafted replies (by message + retrieved examples)
4. RAG corpus + embeddings + FAISS index

**Cache location**: `cache/pipeline/`

**Clear cache**:
```bash
Remove-Item -Recurse -Force cache\pipeline
```

**Rebuild**:
```bash
python scripts\run_pipeline.py --build-corpus --force-rebuild
```

---

## Sanity Testing

Before evaluation, test on known cases:

### Test 1: Delivery Status (Should Auto-Handle)

```bash
python scripts\run_pipeline.py --test "Where is my package? Order #12345"
```

**Expected**:
- Intent: `delivery_status_inquiry`
- Confidence: `high`
- Grounding: >0.7 (common query)
- Routing: `auto_handle`

---

### Test 2: Wrong Item (Should Escalate)

```bash
python scripts\run_pipeline.py --test "Received wrong item - ordered blue, got red"
```

**Expected**:
- Intent: `order_issue`
- Confidence: `high`
- Routing: `escalate` (order issues default escalate)

---

### Test 3: Refund Request (Should Escalate)

```bash
python scripts\run_pipeline.py --test "I want a refund for this defective product"
```

**Expected**:
- Intent: `refund_return_request`
- Confidence: `high`
- Routing: `escalate` (financial/policy risk)

---

### Test 4: Venting (Should Escalate)

```bash
python scripts\run_pipeline.py --test "This is ridiculous! Worst service ever!"
```

**Expected**:
- Intent: `complaint_no_action`
- Confidence: `medium` or `high`
- Routing: `escalate` (escalate-prone intent)

---

### Test 5: Safety Flagged (Must Escalate)

```bash
python scripts\run_pipeline.py --test "I'm going to kill myself if this isn't resolved"
```

**Expected**:
- Intent: Any
- Routing: `escalate`
- Routing reason: "Safety flagged: Crisis keyword detected"
- Safety flagged: `true`

---

### Test 6: Non-English (Must Escalate)

```bash
python scripts\run_pipeline.py --test "Où est mon colis?"
```

**Expected**:
- Intent: Any
- Routing: `escalate`
- Routing reason: "Non-English message (out of scope)"
- Language flagged: `true`

---

## Troubleshooting

**"GOOGLE_API_KEY not found"**
→ Set in `.env` file: `GOOGLE_API_KEY=...`

**"GROQ_API_KEY not found"**
→ Set in `.env` file: `GROQ_API_KEY=...`

**"Corpus not built"**
→ Run `python scripts\run_pipeline.py --build-corpus` first

**"GOLDEN SET LEAKAGE DETECTED"**
→ Critical error. Corpus build should NEVER include golden-set threads. Report this as a bug.

**Rate limit errors (429)**
→ Caching should prevent this. If hitting limits, increase `min_request_interval` in classifier/drafter.

**Low retrieval similarity across the board**
→ Check corpus built correctly. Expected top similarity >0.7 for common queries.

**Intent classifications seem wrong**
→ Check `approved_taxonomy.json` is correct version (8 intents, locked 2026-09-09).
→ Try `--no-cache` to force fresh classification.

---

## Next Steps

After sanity testing:

1. **Evaluation harness** (`scripts/09_evaluate_classifier.py` - NOT YET CREATED)
   - Run classifier on golden set (197 hand-labeled threads)
   - Compute accuracy, per-class F1, routing precision/recall
   - Compare to baselines (majority class, keyword rules)

2. **Failure analysis** (`scripts/10_failure_analysis.py` - NOT YET CREATED)
   - Top 5 failure modes with real examples
   - Confusion matrix for intent classification
   - Routing disagreement cases (system vs human)

3. **Report generation** (`scripts/11_generate_report.py` - NOT YET CREATED)
   - Problem framing
   - Results vs baselines
   - "What's misleading" section
   - Decision log

---

## File Structure

```
.
├── src/
│   ├── intent_classifier.py      # Gemini few-shot classifier
│   ├── rag_retriever.py          # sentence-transformers + FAISS
│   ├── reply_drafter.py          # Groq grounded generation
│   ├── router.py                 # Routing logic
│   ├── safety_filters.py         # (existing)
│   └── language_filter.py        # (existing)
│
├── scripts/
│   └── run_pipeline.py           # End-to-end pipeline script
│
├── cache/
│   └── pipeline/
│       ├── classifier_cache/     # Intent classification cache
│       ├── rag_cache/            # Corpus, embeddings, retrieval cache
│       └── drafter_cache/        # Reply drafting cache
│
├── golden_set/
│   ├── approved_taxonomy.json    # 8-intent taxonomy (locked)
│   ├── unlabeled_sample.jsonl    # 197 threads (EXCLUDED from RAG)
│   └── labeled.jsonl             # Hand-labeled ground truth
│
├── test_messages.txt             # Sample test messages
└── .env                          # API keys (not committed)
```

---

**System ready for sanity testing. Evaluation harness comes next.**
