#!/usr/bin/env python3
"""
Convenience script: Run all stages needed for brand selection.

Usage:
    python run_brand_analysis.py           # Full dataset
    python run_brand_analysis.py --test    # Small sample (10k rows)
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_command(cmd, description):
    """Run a command and handle errors."""
    print("\n" + "=" * 70)
    print(f"⚙️  {description}")
    print("=" * 70)
    print(f"Running: {' '.join(cmd)}")
    print()
    
    result = subprocess.run(cmd, cwd=Path.cwd())
    
    if result.returncode != 0:
        print(f"\n❌ Command failed with exit code {result.returncode}")
        print(f"   Stopping pipeline.")
        sys.exit(result.returncode)
    
    print(f"\n✓ {description} complete")
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Run brand selection pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_brand_analysis.py           # Full dataset (~10 min)
  python run_brand_analysis.py --test    # Test on 10k rows (~1 min)
        """
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Test mode: process only 10k rows'
    )
    parser.add_argument(
        '--skip-download',
        action='store_true',
        help='Skip download step (if data already exists)'
    )
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("BRAND SELECTION PIPELINE")
    print("=" * 70)
    if args.test:
        print("⚠️  TEST MODE: Processing only 10,000 rows")
    else:
        print("📊 FULL MODE: Processing entire dataset")
    print("=" * 70)
    
    # Stage 0: Verify
    run_command(
        [sys.executable, "scripts/00_verify_setup.py"],
        "Stage 0: Verify Environment"
    )
    
    # Stage 1: Download (skip if requested)
    if not args.skip_download:
        run_command(
            [sys.executable, "scripts/01_download_data.py"],
            "Stage 1: Download Dataset"
        )
    else:
        print("\n⏭️  Skipping download (--skip-download)")
    
    # Stage 2: Reconstruct threads
    cmd = [sys.executable, "scripts/02_reconstruct_threads.py"]
    if args.test:
        cmd.extend(["--limit", "10000"])
    
    run_command(cmd, "Stage 2: Reconstruct Threads")
    
    # Stage 3: Analyze brands
    run_command(
        [sys.executable, "scripts/03_analyze_brands.py", "--top-n", "10"],
        "Stage 3: Analyze Brands"
    )
    
    # Done
    print("\n" + "=" * 70)
    print("✓ PIPELINE COMPLETE!")
    print("=" * 70)
    print()
    print("Next steps:")
    print("  1. Review outputs/brand_analysis.json")
    print("  2. Check console output above for brand recommendation")
    print("  3. Confirm your brand choice")
    print()
    print("Files generated:")
    print("  - data/raw/twcs.csv (downloaded data)")
    print("  - data/processed/threads.jsonl (reconstructed threads)")
    print("  - outputs/brand_analysis.json (brand rankings)")
    print()


if __name__ == "__main__":
    main()
