# AI Customer Support Agent — AmazonHelp (Twitter Dataset)

> Take-home assignment: an AI support agent for AmazonHelp, built and evaluated
> against 150 hand-labeled real customer support conversations from the
> "Customer Support on Twitter" Kaggle dataset. See `REPORT.md` for full
> results, failure analysis, and decision log.

**Status**: Complete. Golden set: 150/197 sampled threads labeled. Evaluation
run on 60 examples (gated by free-tier API daily quota limits — see
`REPORT.md` Limitations).

## What This System Does

Given an incoming AmazonHelp customer message, the pipeline:
1. **Classifies intent** into one of 8 brand-derived categories using an LLM
   few-shot classifier (Gemini).
2. **Retrieves similar historical resolutions** from ~10,000 real AmazonHelp
   threads using TF-IDF cosine similarity (local, no API calls).
3. **Drafts a grounded reply** using an LLM (Groq), conditioned on the
   retrieved historical examples.
4. **Decides auto-handle vs. escalate**, applying safety/language checks first
   (hard rules, independent of the classifier), then intent- and
   grounding-strength-based logic, with a stated reason for every decision.

## Technology Stack (as actually shipped)

- **Intent classification & LLM-judge**: Google Gemini, free tier
  (`gemini-flash-lite-latest`)
- **Reply drafting**: Groq, free tier (`openai/gpt-oss-20b`)
- **Retrieval**: scikit-learn TF-IDF + cosine similarity, fully local, no API
  calls, no quota limits. *(Originally planned: local sentence-transformers
  embeddings, abandoned after a persistent unresolved native-library crash;
  then Gemini's embedding API, abandoned after hitting a hard 1,000/day
  free-tier quota. See `REPORT.md` Decision Log items 8–10 for the full story.)*
- **Language**: Python 3.10
- **Cost**: $0 — everything runs on free-tier APIs or fully local components

## Reproducing the Headline Results (~15 minutes)

This assumes you already have the repo cloned and are in its root directory.

### 1. Environment setup (~5 min)

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac

pip install -r requirements.txt
```

**Known dependency pitfalls** (already fixed in `requirements.txt`, documented
here in case you rebuild from scratch): the original `torch`/`sentence-transformers`
combination crashed with a Windows DLL error and was replaced; `groq`'s HTTP
client requires `httpx<0.28`; Groq and Gemini model names in this codebase are
current as of this project's development window — if either provider retires a
model name, `python -c "...genai.list_models()..."` (Gemini) or the Groq
dashboard will show current valid names.

### 2. API keys (~3 min, free, no credit card)

Create a `.env` file in the project root:
```
GOOGLE_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_key
```
- Gemini key: https://aistudio.google.com/app/apikey (create a project, create a key)
- Groq key: https://console.groq.com/keys (Legacy/standard API key)

### 3. Kaggle credentials (~2 min, free, one-time)

1. Create a free Kaggle account
2. https://www.kaggle.com/settings/account → API section → **"Create Legacy API Key"**
   (not the newer "API Tokens" section — this codebase's `kaggle` package
   version expects the legacy `kaggle.json` format)
3. Place the downloaded file at `~/.kaggle/kaggle.json`
   (Windows: `C:\Users\<you>\.kaggle\kaggle.json`)

### 4. Verify and download data (~3 min)

```bash
python scripts/00_verify_setup.py
python scripts/01_download_data.py
```

### 5. Build the RAG corpus (~1 min, fully local)

```bash
python scripts/run_pipeline.py --build-corpus
```

### 6. Reproduce headline evaluation numbers (~3 min)

```bash
python scripts/08_evaluate.py --limit 60
python scripts/09_baselines.py
```

Expected headline numbers (see `REPORT.md` for full breakdown and honest
caveats about small-sample effects):
- Intent accuracy: **53.3%** (vs. 44.0% trivial baseline, 38.0% keyword baseline)
- Routing accuracy: **65.0%** (vs. 72.7% trivial "always escalate" — see
  `REPORT.md` Section 4 for why this is not the flattering result it looks like)

### 7. Reproduce the LLM-judge reply-quality scores (~3 min)

```bash
python scripts/10_llm_judge.py --limit 60
```

Expected: aggregate overall reply quality ≈ 4.44/5 across correctness, tone,
completeness, actionability (see `REPORT.md` for the human-agreement check
against these scores).

### Testing a single message end-to-end

```bash
python scripts/run_pipeline.py --test "Where is my package?"
```

## Project Structure

```
.
├── data/                       # Downloaded and processed data (gitignored)
│   └── processed/threads.jsonl # Reconstructed conversation threads
├── scripts/                    # Pipeline stages, numbered in execution order
│   ├── 00_verify_setup.py
│   ├── 01_download_data.py
│   ├── 02_reconstruct_threads.py
│   ├── 03_analyze_brands.py
│   ├── 04_sample_for_taxonomy.py
│   ├── 05_propose_taxonomy.py
│   ├── 06_refine_taxonomy.py
│   ├── 07_sample_golden_set.py
│   ├── 08_evaluate.py          # Evaluation harness (intent/routing metrics)
│   ├── 09_baselines.py         # Trivial + keyword baselines
│   ├── 10_llm_judge.py         # Reply-quality LLM-judge + human agreement
│   ├── label_golden_set.py     # Interactive CLI labelling tool
│   └── run_pipeline.py         # End-to-end pipeline / entry point
├── src/                        # Core reusable modules
│   ├── intent_classifier.py
│   ├── rag_retriever.py        # TF-IDF retrieval
│   ├── reply_drafter.py
│   ├── router.py
│   ├── safety_filters.py
│   └── language_filter.py
├── golden_set/
│   ├── unlabeled_sample.jsonl  # 197 stratified-sampled threads
│   ├── labeled.jsonl           # 150 hand-labeled examples
│   └── approved_taxonomy.json  # Final 8-intent taxonomy
├── outputs/
│   ├── eval_results.json       # Full evaluation output
│   ├── baseline_results.json
│   ├── judge_results.json
│   └── human_scoring_template.json
├── cache/                       # LLM response cache, gitignored
├── REPORT.md                    # Full report: results, failure analysis, decision log
├── CITATIONS.md                 # Attribution for borrowed code/patterns
└── requirements.txt
```

## Data Handling & Leakage Prevention

- **Golden-set exclusion is a hard runtime assertion, not a comment.**
  `src/rag_retriever.py`'s `build_corpus()` raises `AssertionError` if any
  golden-set thread ID is found in the retrieval corpus.
- The golden set (197 sampled, 150 labeled) is stratified by intent and
  deliberately oversamples rare intents (`account_access_issue`,
  `complaint_no_action`, `prime_membership_inquiry`) relative to their natural
  base rate — see `REPORT.md` Decision Log for why, and Section 4 for the
  reporting implications.
- Non-English messages (~17% of the natural traffic, matching the dataset's
  observed language mix) are out of scope and force-escalated rather than
  processed by the classifier.

## Full Results, Failure Analysis, and Decision Log

See **`REPORT.md`** for:
- Problem framing and explicit scope decisions
- Full results table vs. two baselines
- Top 5 failure modes with real examples and hypotheses
- The mandatory "what's misleading about my headline number" analysis
- What I'd do next with one more week
- A 15-item decision log of non-obvious choices made during development

## Citations

See `CITATIONS.md` for attribution of borrowed code, patterns, and
AI-assistant-generated code throughout this project.
