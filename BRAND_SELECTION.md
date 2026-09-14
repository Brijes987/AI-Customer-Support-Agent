# Brand Selection - Shortlist and Analysis

**Status**: Ready for execution — awaiting data download and analysis results

## Objective

Select ONE brand from the Twitter Customer Support dataset that will be the target for building and evaluating the AI support agent.

## Selection Criteria

The brand analysis script (`scripts/03_analyze_brands.py`) scores brands on a 0-100 scale using:

### 1. Volume Score (30 points)
- **Why**: Need enough data for robust taxonomy derivation, train/eval split, and RAG corpus
- **Threshold**: Saturates at ~10k threads
- **Penalty**: Low-volume brands get proportionally fewer points

### 2. Response Rate (30 points)
- **Why**: Can't learn resolution patterns from brands that don't respond
- **Formula**: (threads with ≥1 brand response) / (total threads)
- **Target**: ≥70% response rate is ideal

### 3. Thread Length Score (20 points)
- **Why**: Too short = overly templated (no learning signal); too long = outliers/complex cases
- **Sweet spot**: 2-6 messages per thread average
- **Penalty**: Heavy for <2, moderate for >6

### 4. Resolution Rate (20 points)
- **Why**: Need threads that actually close with brand response (training signal for "good" resolutions)
- **Formula**: (threads ending with brand response) / (threads with any brand response)
- **Target**: High is better

## Expected Shortlist Candidates

Based on prior knowledge of the dataset, likely top brands:

| Brand | Expected Characteristics |
|-------|-------------------------|
| **AppleSupport** | Very high volume, consistent responses, good resolution patterns |
| **AmazonHelp** | Massive volume, templated but effective responses |
| **Uber_Support** | High volume, varied issue types, active engagement |
| **SpotifyCares** | Moderate-high volume, friendly tone, good multi-turn |
| **Delta** | Airlines support, high volume, clear escalation patterns |
| **TMobileHelp** | Telco support, high volume, billing/tech split |

## Execution Plan

### Step 1: Download and Reconstruct
```bash
# Download dataset (~450 MB)
python scripts/01_download_data.py

# Reconstruct threads (5-10 min on full dataset)
python scripts/02_reconstruct_threads.py

# Or test first on 10k rows
python scripts/02_reconstruct_threads.py --limit 10000
```

### Step 2: Run Brand Analysis
```bash
# Analyze top 10 brands
python scripts/03_analyze_brands.py --top-n 10
```

**Output files**:
- `outputs/brand_analysis.json` — Full ranking with metrics
- Console — Human-readable summary with recommendation

### Step 3: Review Results

The script will output:
1. **Ranked list** with scores and key metrics
2. **Automated recommendation** (top-scored brand)
3. **Justification** based on the scoring criteria

### Step 4: Manual Confirmation

You (the assignment author) will review the shortlist and confirm:
- Does the recommended brand make sense?
- Are there domain-specific reasons to override the score? (e.g., prefer diverse issue types over pure volume)
- Is there any data quality concern visible in the sample threads?

## Decision Factors Beyond the Score

The automated score captures quantity and structure. You should also consider:

### Domain Diversity
- **Broad issue types** (better for taxonomy richness) vs. narrow/repetitive
- Example: AppleSupport covers hardware, software, billing, account issues
- Counter-example: A brand that only handles delivery tracking

### Escalation Signals
- Do threads show clear "escalate to human" patterns? (e.g., asking for DMs, providing case numbers)
- This is critical for the routing decision component

### Tone Consistency
- Brand voice should be identifiable but not so rigid that replies are pure templates
- Need variation to evaluate reply quality

### Data Quality
- Are there obvious data artifacts? (e.g., spam threads, bot conversations)
- Thread reconstruction errors would show up as extremely long threads or nonsensical message orders

## Post-Selection

Once brand is confirmed:
1. Filter dataset to selected brand only → saves to `data/processed/{brand}_threads.jsonl`
2. Sample threads for intent taxonomy derivation (next stage)
3. Design non-overlapping splits:
   - **RAG corpus**: Historical resolved threads (70%)
   - **Training/dev**: For classifier tuning if needed (15%)
   - **Golden eval set**: Holdout for final evaluation (15%)

## Leakage Prevention Note

**Critical**: The golden evaluation set must NEVER appear in:
- RAG retrieval corpus
- Few-shot prompting examples
- Classifier training data

This will be enforced in code via explicit date/ID-based splits, documented in comments.

---

**Next step**: Run the analysis and await your confirmation of the brand choice.
