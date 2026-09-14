# Setup and Execution Guide

## Initial Setup

### 1. Install Python Dependencies

```bash
# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Kaggle API

1. Create Kaggle account: https://www.kaggle.com
2. Generate API token: https://www.kaggle.com/settings/account → API → "Create New Token"
3. Place `kaggle.json` at: `C:\Users\<YourUsername>\.kaggle\kaggle.json`

### 3. Download Dataset

```bash
python scripts/01_download_data.py
```

Expected output: `data/raw/twcs.csv` (~450 MB, ~3M rows)

## Brand Selection Workflow

### Step 1: Reconstruct Threads

```bash
# Full dataset
python scripts/02_reconstruct_threads.py

# Or test on 10k rows first
python scripts/02_reconstruct_threads.py --limit 10000
```

Output: `data/processed/threads.jsonl`

### Step 2: Analyze Brands

```bash
python scripts/03_analyze_brands.py --top-n 10
```

Output: 
- Console: Ranked brand analysis with justification
- File: `outputs/brand_analysis.json`

### Step 3: Review and Confirm

Review the brand shortlist in the console output. The script will recommend the top-scoring brand based on:
- Volume (enough data for taxonomy + train/eval split)
- Response rate (need actual resolutions to learn from)
- Thread quality (reasonable lengths, not too templated)
- Resolution rate (threads that close properly)

**Expected brands in shortlist:**
- AppleSupport
- AmazonHelp  
- Uber_Support
- SpotifyCares
- Delta
- TMobileHelp

Once you confirm a brand, proceed to intent taxonomy derivation.

## Testing Commands

All scripts support `--limit N` for testing on small samples:

```bash
# Test thread reconstruction on 1000 tweets
python scripts/02_reconstruct_threads.py --limit 1000

# This will analyze whatever threads were built
python scripts/03_analyze_brands.py
```

## Expected Timeline

- **Setup + download**: 10-15 minutes
- **Thread reconstruction** (full dataset): 5-10 minutes  
- **Brand analysis**: 2-3 minutes
- **Review + confirm**: You decide!

## Troubleshooting

### Kaggle credentials not found
- Ensure `kaggle.json` is at the correct path
- Check file permissions (should not be world-readable on Linux/Mac)

### Module not found errors
- Activate virtual environment: `venv\Scripts\activate`
- Re-run: `pip install -r requirements.txt`

### Out of memory during thread reconstruction
- Use `--limit` flag to process a subset
- Alternatively, increase system swap/virtual memory

## Next Steps

After brand confirmation, the workflow continues with:
1. Intent taxonomy derivation (from brand's actual data)
2. Golden set sampling strategy
3. Hand-labelling (you will do this manually)
4. Classifier, RAG, routing system
5. Evaluation harness
6. Baselines and final report
