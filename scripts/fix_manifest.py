#!/usr/bin/env python3
"""
Utility: Manually create data manifest if download script didn't create it.

Usage:
    python scripts/fix_manifest.py
"""

import json
from pathlib import Path


def find_twcs_csv():
    """Search for twcs.csv in common locations."""
    search_paths = [
        Path("data/raw/twcs.csv"),
        Path("data/raw/twcs/twcs.csv"),
    ]
    
    for path in search_paths:
        if path.exists():
            return path
    
    # Recursive search as last resort
    raw_dir = Path("data/raw")
    if raw_dir.exists():
        for csv in raw_dir.rglob("twcs.csv"):
            return csv
    
    return None


def main():
    print("Searching for twcs.csv...")
    
    csv_path = find_twcs_csv()
    
    if not csv_path:
        print("❌ Could not find twcs.csv")
        print("   Make sure you've run: python scripts/01_download_data.py")
        return 1
    
    file_size_mb = csv_path.stat().st_size / (1024 * 1024)
    print(f"✓ Found: {csv_path} ({file_size_mb:.1f} MB)")
    
    # Create manifest
    manifest = {
        "dataset": "customer-support-on-twitter",
        "csv_path": str(csv_path.absolute()),
        "csv_relative": str(csv_path),
    }
    
    manifest_path = Path("data/data_manifest.json")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"✓ Created manifest: {manifest_path}")
    print("\nManifest contents:")
    print(json.dumps(manifest, indent=2))
    
    return 0


if __name__ == "__main__":
    exit(main())
