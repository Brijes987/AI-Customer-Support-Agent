# Bug Fix: Nested CSV Path Issue

## Problem

The Kaggle dataset extracts to a nested structure:
```
data/raw/twcs/twcs.csv
```

But scripts expected:
```
data/raw/twcs.csv
```

This caused:
1. `01_download_data.py` reported only `sample.csv (0.0 MB)` instead of the 516MB `twcs.csv`
2. `02_reconstruct_threads.py` failed with `FileNotFoundError`

## Solution

### 1. Download Script (`01_download_data.py`)
- **Uses `rglob()` instead of `glob()`** to recursively find `twcs.csv`
- **Creates data manifest** (`data/data_manifest.json`) recording actual CSV location
- **Checks multiple locations** before download to detect existing file
- **Lists all files recursively** after download to verify extraction

### 2. Thread Reconstruction Script (`02_reconstruct_threads.py`)
- **Added `find_csv_path()` function** that checks:
  1. Data manifest (primary source of truth)
  2. Default path (if user provided `--input`)
  3. Common nested locations (fallback)
- **Clear error messages** listing all attempted paths if file not found

### 3. New Utility Script (`scripts/fix_manifest.py`)
- **Manual manifest creator** if download script didn't create it
- **Recursive search** for `twcs.csv` in data directory
- **Can be run standalone** to fix path issues

## Data Manifest Format

`data/data_manifest.json`:
```json
{
  "dataset": "customer-support-on-twitter",
  "csv_path": "C:\\Users\\HP\\Desktop\\Hiver\\data\\raw\\twcs\\twcs.csv",
  "csv_relative": "raw\\twcs\\twcs.csv"
}
```

This decouples path assumptions from code — downstream scripts read the manifest instead of hardcoding paths.

## Testing

You can now run:
```bash
python run_brand_analysis.py --test
```

This should work regardless of whether Kaggle extracted to:
- `data/raw/twcs.csv` (flat)
- `data/raw/twcs/twcs.csv` (nested)

## Files Changed

- ✏️ `scripts/01_download_data.py` — Recursive search, manifest creation
- ✏️ `scripts/02_reconstruct_threads.py` — Path resolution via manifest
- ✏️ `.gitignore` — Keep manifest (exclude data)
- ➕ `scripts/fix_manifest.py` — Manual manifest creator utility

## Next Steps

Re-run the pipeline:
```bash
python run_brand_analysis.py --test
```

Expected output:
- ✓ Stage 1: Uses existing `twcs.csv`, creates manifest
- ✓ Stage 2: Reads manifest, reconstructs threads from 10k rows
- ✓ Stage 3: Analyzes brands, outputs rankings

---

**Status**: Ready for testing
