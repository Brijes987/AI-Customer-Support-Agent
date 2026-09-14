# Code Citations and References

This file tracks all external code, prompts, algorithms, and patterns borrowed
or adapted from external sources, as required by the assignment rules. Updated
to reflect the final system as shipped (see `REPORT.md` for the full
development history and decision log).

## Dataset

- **Customer Support on Twitter**: Kaggle dataset `thoughtvector/customer-support-on-twitter`
  - URL: https://www.kaggle.com/datasets/thoughtvector/customer-support-on-twitter
  - License: Unknown (publicly available on Kaggle)
  - Used for: Primary data source

- **Banking77** (optional, not used in final system): Hugging Face dataset `PolyAI/banking77`
  - URL: https://huggingface.co/datasets/PolyAI/banking77
  - License: CC BY 4.0
  - Considered as an optional intent-classifier reference; not actually used in
    the final taxonomy or classifier, since AmazonHelp's own data provided
    sufficient real examples for taxonomy derivation.

## Libraries and APIs (as actually shipped)

- **Kaggle API**: Official Python client for dataset downloads
  - Docs: https://github.com/Kaggle/kaggle-api
  - Used in: `scripts/01_download_data.py`
  - Note: this project uses the **legacy** API key format (`kaggle==1.5.16`),
    not Kaggle's newer API Tokens system, since the installed package version
    expects the legacy `kaggle.json` format.

- **Google Generative AI (Gemini)**: free tier
  - Docs: https://ai.google.dev/
  - Used for: **intent classification** (`src/intent_classifier.py`) and
    **LLM-as-judge reply-quality scoring** (`scripts/10_llm_judge.py`)
  - Model: `gemini-flash-lite-latest`. An earlier model name
    (`gemini-1.5-flash`) used during development was deprecated by Google
    partway through the project and had to be swapped for a current model
    name, confirmed via `genai.list_models()`.

- **Groq**: free-tier fast inference API
  - Docs: https://groq.com/
  - Used for: **reply drafting** (`src/reply_drafter.py`)
  - Model: `openai/gpt-oss-20b`. An earlier model name (`llama-3.1-8b-instant`)
    used during development was retired by Groq partway through the project
    and had to be swapped, confirmed via the Groq models API.
  - Note: `openai/gpt-oss-20b` is a reasoning-style model that consumes tokens
    on internal reasoning before producing a visible reply. An initial
    `max_tokens=200` limit was too tight and intermittently produced empty
    replies; increased to `max_tokens=600` to fix this (see `REPORT.md`
    Decision Log item 14).

- **scikit-learn** (`TfidfVectorizer`, `cosine_similarity`): standard library
  functions, not custom algorithms
  - Docs: https://scikit-learn.org/
  - Used for: **RAG retrieval** (`src/rag_retriever.py`)
  - This replaced two earlier, abandoned approaches:
    1. **sentence-transformers** (local embeddings) — abandoned after a
       persistent, unresolved native crash (`sentence_transformers.models`
       import failure) that survived three package version attempts
       (2.2.2, 2.7.0, 2.4.0) with no combination of torch/transformers/
       huggingface-hub versions resolving it on the Windows development
       environment.
    2. **Gemini embedding API** (`models/gemini-embedding-001`) — abandoned
       after hitting a hard 1,000 requests/day free-tier quota partway
       through building the planned RAG corpus.
  - See `REPORT.md` Decision Log items 8–11 for the full story and the
    resulting trade-off (TF-IDF captures keyword overlap, not semantic
    paraphrase similarity).

- **FAISS**: considered, not used in the final system. Originally planned
  for vector similarity search alongside sentence-transformers embeddings;
  dropped when the embedding approach itself was abandoned, since TF-IDF
  vectors are compared directly via `sklearn.metrics.pairwise.cosine_similarity`
  without needing a separate vector index at this corpus size (~10,000 entries).

- **httpx**: pinned to `<0.28` in `requirements.txt`. A newer `httpx` release
  removed a `proxies` argument that the installed `groq` package version
  still passed internally, causing `TypeError: Client.__init__() got an
  unexpected keyword argument 'proxies'`. Downgrading `httpx` resolved this
  without needing to change the `groq` package version.

- **torch / sentence-transformers version history**: `requirements.txt`
  originally left `torch` unpinned, which pulled in `torch==2.14.0` as a
  transitive dependency and caused a Windows DLL load failure
  (`OSError: [WinError 1114]`). This was worked around by pinning
  `torch==2.1.2+cpu` (CPU-only wheel) and iterating through several
  `sentence-transformers` versions, none of which resolved the deeper
  `sentence_transformers.models` import crash — ultimately leading to the
  TF-IDF pivot described above. `torch` remains in the environment as an
  indirect dependency of other installed packages but is not used directly
  by the final retrieval system.

## Algorithms and Patterns

### Thread Reconstruction (`scripts/02_reconstruct_threads.py`)
- **Algorithm**: Depth-first traversal of the `in_response_to_tweet_id` /
  `response_tweet_id` reply graph.
- **Source**: Standard graph traversal pattern, adapted for Twitter reply
  chains; implementation is original, not copied from a specific source.
- **Known limitation** (see `REPORT.md` Failure Mode 5): this structural
  approach has no semantic check that reconstructed threads are actually
  topically coherent, occasionally merging unrelated tweets that happen to
  share a reply-chain ancestor, or missing a thread's true opening message.

### Path Manifest System (`scripts/01_download_data.py`, `02_reconstruct_threads.py`)
- **Pattern**: A small JSON manifest recording the actual on-disk location of
  the downloaded dataset, read by downstream scripts instead of hardcoding a
  path.
- **Source**: Original implementation, added after discovering that Kaggle's
  zip extracts the real CSV into a nested subdirectory
  (`data/raw/twcs/twcs.csv`), which an earlier hardcoded path
  (`data/raw/twcs.csv`) did not account for.

### Brand Scoring (`scripts/03_analyze_brands.py`)
- **Algorithm**: Multi-criteria scoring (volume, multi-turn engagement rate,
  thread length, resolution rate), with template-diversity reported
  separately as a diagnostic (not folded into the score).
- **Source**: Original heuristic design based on assignment requirements;
  criteria weights chosen based on judgment, not a cited external source.
- **Revision history**: an initial "response rate" criterion was discovered to
  be 100% for every brand by construction (thread reconstruction only keeps
  threads that already have a brand response), and was replaced with
  multi-turn engagement rate, which has real variance across brands.
- **Template diversity**: an initial exact-string uniqueness measure was
  discovered to be near-100% for every brand due to per-customer
  personalization (@mentions, order numbers) making near-identical templated
  replies look "unique." Fixed by normalizing replies (stripping @mentions,
  URLs, and numeric IDs via standard regex patterns) before comparing for
  template similarity.

### Safety Filters (`src/safety_filters.py`)
- **Pattern**: Pre-classification keyword/regex checks for crisis language,
  threats, PII exposure, and severe abusive language, forcing escalation
  independent of the intent classifier.
- **Source**: Original implementation; keyword lists and PII regex patterns
  (SSN format, credit-card-like digit sequences) are standard patterns, not
  copied from a specific external safety-filter implementation.
- **Known limitations** (see `REPORT.md` Failure Mode 4): this is a
  keyword-based filter, not a trained classifier. It produced at least one
  confirmed false positive (a sarcastic message about package theft flagged as
  "severe abusive language") during evaluation, and likely has false negatives
  for creatively-phrased abuse not matching the exact keyword list (e.g. "U
  idiot" does not match the list's more specific phrases like "fucking idiot").

### Language Detection (`src/language_filter.py`)
- **Pattern**: Heuristic detection using Unicode script ranges (Cyrillic,
  Arabic, Devanagari, CJK, etc.) plus common-word matching for
  French/Spanish/German/Portuguese.
- **Source**: Original implementation; Unicode ranges are standard published
  ranges, not copied from a specific library. Deliberately not using
  `langdetect` or a similar library, to keep the filter dependency-free and
  fast for this scope.
- **Known limitation**: not a rigorous language detector — occasionally
  misses non-English messages that use only Latin-script transliteration
  (e.g. romanized Hindi), and does not attempt language detection on very
  short messages with ambiguous content.

### LLM Response Caching (used throughout `src/intent_classifier.py`,
`src/rag_retriever.py`, `src/reply_drafter.py`)
- **Pattern**: SHA-256 hash of input text (plus retrieved-example thread IDs,
  where relevant) as a cache key, storing the JSON response on disk.
- **Source**: Standard caching pattern; implementation is original.

### Evaluation Harness (`scripts/08_evaluate.py`)
- **Metrics implementation**: Precision/recall/F1 and confusion-matrix
  computation are implemented directly (not via `sklearn.metrics`), to avoid
  a dependency mismatch with the exact label set used across intent
  categories with small sample sizes. Formulas used are the standard
  precision = TP/(TP+FP), recall = TP/(TP+FN), F1 = harmonic mean definitions.
- **Grounding-threshold calibration approach**: comparing the empirical
  distribution of `grounding_strength` scores between human-labeled
  `auto_handle` and `escalate` examples, and choosing a threshold between the
  two group means, is an original approach for this project, not adapted from
  a specific paper or library.

### Baselines (`scripts/09_baselines.py`)
- **Trivial baseline**: always predicting the majority class — a standard,
  well-known baseline concept in ML evaluation, not attributable to a specific
  source.
- **Simple keyword baseline**: hand-written keyword/rule lists for intent and
  routing, original implementation for this project.

### LLM-as-Judge (`scripts/10_llm_judge.py`)
- **Pattern**: using a separate LLM (Gemini) to score generated text
  (drafted replies from Groq) against an explicit rubric, then measuring
  agreement against independent human scoring on a subset — this is a
  well-established evaluation pattern in current LLM application practice
  (sometimes called "LLM-as-judge"), not attributable to one specific paper;
  the rubric dimensions (correctness/groundedness, tone, completeness,
  actionability) and prompt wording are original for this project.

## AI Coding Assistant Usage

This entire codebase was developed with AI assistance (Kiro, using Claude
models, plus separate assistance for debugging and report-writing). All
generated code was reviewed, tested against real data, and iterated on when
it produced incorrect or misleading results — including catching and
correcting several cases where an AI assistant's own summary of its work
("all examples passed validation", "reply diversity fixed") did not match
what the actual output showed on inspection (see `REPORT.md` for specific
examples, e.g. the taxonomy-refinement iterations and the stale-cache empty-reply
bug). I can explain and modify any part of this codebase during live review.

---

**Last updated**: reflects the final system as of project completion.
**Maintained by**: Assignment author
