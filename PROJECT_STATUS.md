# Project Status

**Assignment**: AI Customer Support Agent (Twitter Dataset)  
**Last Updated**: 2026-09-09  
**Current Phase**: Brand Selection

---

## Completed ✓

### Project Structure
- [x] Repository initialized
- [x] Directory structure created
- [x] Dependencies specified (`requirements.txt`)
- [x] `.gitignore` configured (data/cache ignored, golden set preserved)
- [x] Documentation framework (README, SETUP, CITATIONS)

### Stage 0: Environment Setup
- [x] Verification script (`scripts/00_verify_setup.py`)
- [x] Setup instructions (SETUP.md)

### Stage 1: Data Download
- [x] Kaggle download script (`scripts/01_download_data.py`)
- [x] Graceful failure with clear instructions if credentials missing
- [x] File size reporting and duplicate detection
- [x] Manifest system for nested paths

### Stage 2: Thread Reconstruction  
- [x] Graph-based thread builder (`scripts/02_reconstruct_threads.py`)
- [x] DFS traversal with proper chronological sorting
- [x] Manifest-based path resolution
- [x] `--limit N` flag for testing on subsets
- [x] Statistics reporting (thread counts, lengths)

### Stage 3: Brand Analysis
- [x] Multi-criteria scoring function (`scripts/03_analyze_brands.py`)
- [x] Volume, multi-turn engagement, thread quality, resolution rate metrics
- [x] Template diversity (normalization-based, not exact-string)
- [x] Automated ranking with justification
- [x] JSON output for downstream use
- [x] Full dataset analysis completed (798k threads, 108 brands)
- [x] **Brand confirmed: AmazonHelp** (82,555 threads, 90.8% template diversity)

### Stage 4: Thread Sampling for Taxonomy
- [x] Stratified sampling script (`scripts/04_sample_for_taxonomy.py`)
- [x] Sample by length, resolution status, engagement depth

### Stage 5: Taxonomy Proposal
- [x] Keyword analysis script (`scripts/05_propose_taxonomy.py`)
- [x] Pattern detection and intent clustering

### Documentation
- [x] Brand selection criteria (BRAND_SELECTION.md)
- [x] Citations framework (CITATIONS.md)
- [x] Scoring fixes (SCORING_FIX.md, TEMPLATE_NORMALIZATION.md)
- [x] Taxonomy derivation guide (TAXONOMY_DERIVATION.md)
- [x] Project status tracking (this file)

---

## In Progress ⏳

### Intent Taxonomy Derivation
- [ ] **YOU**: Run sampling script (`run_taxonomy_derivation.bat` or manual commands)
- [ ] **YOU**: Review `outputs/taxonomy_sample_display.txt` (actual customer messages)
- [ ] **YOU**: Review `outputs/proposed_taxonomy.json` (automated proposal)
- [ ] **YOU**: Confirm or adjust taxonomy (6-10 intents)
- [ ] **ME**: Wait for taxonomy confirmation before proceeding to golden set

---

## Planned 📋

### Stage 4: Intent Taxonomy Derivation
- [ ] Sample representative threads from chosen brand
- [ ] Cluster/analyze common issue types
- [ ] Define 6-10 intent categories with examples
- [ ] **YOU**: Review and confirm taxonomy

### Stage 5: Golden Set Sampling
- [ ] Design stratified sampling strategy (by intent, length, thread complexity)
- [ ] Extract 150-250 threads for hand-labelling
- [ ] Build labelling interface (CLI or spreadsheet with validation)
- [ ] Generate labelling guidelines document
- [ ] **YOU**: Hand-label all examples (~2-3 hours)

### Stage 6: Data Splitting (Anti-Leakage)
- [ ] Split brand data into RAG corpus / dev / golden eval
- [ ] Ensure zero overlap (document in code comments)
- [ ] Validate splits (automated check for leakage)

### Stage 7: RAG System
- [ ] Build embedding index (sentence-transformers + FAISS)
- [ ] Implement retrieval (top-k similar historical threads)
- [ ] Test retrieval quality (hit rate metric)

### Stage 8: Intent Classification
- [ ] Gemini-based classifier with few-shot prompting
- [ ] LLM response caching (hash → JSON)
- [ ] Rate limiting and backoff
- [ ] `--limit N` flag for testing

### Stage 9: Reply Drafting
- [ ] RAG-grounded prompt construction
- [ ] Gemini-based reply generation
- [ ] Caching and rate limiting

### Stage 10: Routing Decision
- [ ] Auto-handle vs. escalate classifier
- [ ] Confidence scoring
- [ ] Reason generation (required for every decision)

### Stage 11: Baselines
- [ ] **Trivial**: Majority-class intent + canned reply
- [ ] **Simple**: Keyword rules + non-RAG LLM
- [ ] Run both on golden set

### Stage 12: Evaluation Harness
- [ ] Intent classification metrics (accuracy, per-class F1, macro F1)
- [ ] Routing metrics (precision/recall, treat auto-handle as positive class)
- [ ] LLM-as-judge (Groq) with explicit rubric
- [ ] Human-judge agreement study (you score ~30-40, compute kappa/correlation)

### Stage 13: Failure Analysis
- [ ] Run main system on golden set
- [ ] Log all errors
- [ ] Identify top 5 failure modes with real examples
- [ ] Write hypotheses for each

### Stage 14: Report Assembly
- [ ] Problem framing and scope cuts
- [ ] Results vs. baselines (side-by-side table)
- [ ] Failure analysis section
- [ ] "What is misleading about my headline number?" (mandatory critical section)
- [ ] What I'd do next with one more week

### Stage 15: Decision Log
- [ ] List 10-15 non-obvious decisions made during project
- [ ] Brief rationale for each
- [ ] Examples: Why this brand? Why this taxonomy size? Why this retrieval strategy? How was leakage prevented?

### Stage 16: Final Polish
- [ ] README with 15-minute reproduction steps
- [ ] Verify all outputs are generated correctly
- [ ] Clean up code comments
- [ ] Final CITATIONS.md audit

---

## Key Constraints (Reminders)

- **Budget**: $0 total — free-tier APIs only
- **LLMs**: Gemini (drafting/classification), Groq (judge) — different providers intentional
- **Embeddings**: sentence-transformers (local, free)
- **Caching**: All LLM responses cached by input hash
- **Rate limiting**: Built into every API call
- **Testing**: Every stage has `--limit N` flag
- **Leakage prevention**: Golden set never in RAG corpus or prompts
- **Baselines**: Must be real enough that beating them is meaningful
- **Evaluation**: Rigor is first-class deliverable, not afterthought

---

## Immediate Next Steps

**For you**:
1. Run `python scripts/00_verify_setup.py` to check environment
2. Create Kaggle API credentials (see SETUP.md)
3. Run `python scripts/01_download_data.py` to fetch dataset
4. Run `python scripts/02_reconstruct_threads.py` to build threads
5. Run `python scripts/03_analyze_brands.py` to generate shortlist
6. Review the brand rankings and **confirm your choice**

**For me**:
- Waiting for your brand confirmation
- Will not proceed to intent taxonomy until you approve the brand
- Ready to answer questions about the analysis or adjust scoring criteria if needed

---

**Questions or concerns?** Let me know before proceeding!
