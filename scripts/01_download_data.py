#!/usr/bin/env python3
"""
Stage 1: Download Customer Support on Twitter dataset from Kaggle.

Requires Kaggle API credentials at ~/.kaggle/kaggle.json
Fails gracefully with clear setup instructions if credentials are missing.
"""

import os
import sys
import json
from pathlib import Path

def check_kaggle_credentials():
    """Check if Kaggle credentials exist and provide setup instructions if missing."""
    kaggle_dir = Path.home() / ".kaggle"
    kaggle_json = kaggle_dir / "kaggle.json"
    
    if not kaggle_json.exists():
        print("❌ Kaggle API credentials not found!")
        print()
        print("Setup instructions:")
        print("1. Create a Kaggle account at https://www.kaggle.com")
        print("2. Go to https://www.kaggle.com/settings/account")
        print("3. Scroll to 'API' section and click 'Create New Token'")
        print("4. This downloads kaggle.json — place it at:")
        print(f"   {kaggle_json}")
        print()
        print("5. On Linux/Mac, set permissions: chmod 600 ~/.kaggle/kaggle.json")
        print()
        sys.exit(1)
    
    print(f"✓ Found Kaggle credentials at {kaggle_json}")


def _write_path_manifest(download_path, csv_path):
    """
    Write a manifest file recording the actual CSV location.
    This allows downstream scripts to find the file without hardcoding paths.
    """
    manifest = {
        "dataset": "customer-support-on-twitter",
        "csv_path": str(csv_path.absolute()),
        "csv_relative": str(csv_path.relative_to(download_path.parent)),
    }
    
    manifest_path = download_path.parent / "data_manifest.json"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"\n✓ Wrote path manifest: {manifest_path}")



def download_dataset():
    """Download the Customer Support on Twitter dataset."""
    import kaggle
    
    dataset_name = "thoughtvector/customer-support-on-twitter"
    download_path = Path("data/raw")
    download_path.mkdir(parents=True, exist_ok=True)
    
    print(f"\n📦 Downloading dataset: {dataset_name}")
    print(f"   Destination: {download_path.absolute()}")
    print()
    
    # Check if already downloaded (Kaggle extracts to nested twcs/ folder)
    possible_locations = [
        download_path / "twcs.csv",
        download_path / "twcs" / "twcs.csv",
    ]
    
    for expected_file in possible_locations:
        if expected_file.exists():
            file_size_mb = expected_file.stat().st_size / (1024 * 1024)
            print(f"⚠️  Dataset already exists ({file_size_mb:.1f} MB)")
            print(f"   {expected_file}")
            response = input("\nRe-download anyway? (y/N): ").strip().lower()
            if response != 'y':
                print("Skipping download.")
                _write_path_manifest(download_path, expected_file)
                return
            break
    
    try:
        kaggle.api.dataset_download_files(
            dataset_name,
            path=str(download_path),
            unzip=True,
            quiet=False
        )
        print("\n✓ Download complete!")
        
        # Find the actual CSV file (Kaggle may extract to nested folder)
        csv_files = list(download_path.rglob("twcs.csv"))
        
        if not csv_files:
            print("\n⚠️  Warning: twcs.csv not found after extraction")
            print("   Listing all downloaded files:")
            for f in sorted(download_path.rglob("*")):
                if f.is_file():
                    size_mb = f.stat().st_size / (1024 * 1024)
                    print(f"  - {f.relative_to(download_path)} ({size_mb:.1f} MB)")
        else:
            actual_csv = csv_files[0]
            print(f"\n✓ Found dataset at: {actual_csv}")
            file_size_mb = actual_csv.stat().st_size / (1024 * 1024)
            print(f"  Size: {file_size_mb:.1f} MB")
            
            # Write manifest for downstream scripts
            _write_path_manifest(download_path, actual_csv)
        
        # List all downloaded files
        print("\nAll downloaded files:")
        for f in sorted(download_path.rglob("*")):
            if f.is_file():
                size_mb = f.stat().st_size / (1024 * 1024)
                rel_path = f.relative_to(download_path)
                print(f"  - {rel_path} ({size_mb:.1f} MB)")
    
    except Exception as e:
        print(f"\n❌ Download failed: {e}")
        sys.exit(1)


def main():
    print("=" * 60)
    print("Stage 1: Download Kaggle Dataset")
    print("=" * 60)
    
    check_kaggle_credentials()
    download_dataset()
    
    print("\n" + "=" * 60)
    print("✓ Stage 1 complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
