#!/usr/bin/env python3
"""
Stage 0: Verify environment setup and dependencies.

Run this first to ensure everything is configured correctly.
"""

import sys
from pathlib import Path


def check_python_version():
    """Check Python version is 3.9+"""
    version = sys.version_info
    if version < (3, 9):
        print(f"❌ Python {version.major}.{version.minor} detected")
        print(f"   Requires Python 3.9+")
        return False
    print(f"✓ Python {version.major}.{version.minor}.{version.micro}")
    return True


def check_dependencies():
    """Check if required packages are installed."""
    required = [
        ('pandas', 'Data processing'),
        ('numpy', 'Numerical operations'),
        ('kaggle', 'Dataset download'),
        ('tqdm', 'Progress bars'),
        ('sklearn', 'Evaluation metrics'),
    ]
    
    missing = []
    for package, purpose in required:
        try:
            __import__(package)
            print(f"✓ {package:20s} ({purpose})")
        except ImportError:
            print(f"❌ {package:20s} ({purpose}) - NOT FOUND")
            missing.append(package)
    
    return len(missing) == 0, missing


def check_kaggle_credentials():
    """Check Kaggle API credentials exist."""
    kaggle_json = Path.home() / ".kaggle" / "kaggle.json"
    if kaggle_json.exists():
        print(f"✓ Kaggle credentials found at {kaggle_json}")
        return True
    else:
        print(f"⚠️  Kaggle credentials NOT found")
        print(f"   Expected location: {kaggle_json}")
        print(f"   Run scripts/01_download_data.py for setup instructions")
        return False


def check_directories():
    """Check expected directory structure."""
    dirs = [
        'data',
        'scripts',
        'src',
        'cache',
        'models',
        'outputs',
        'golden_set',
    ]
    
    all_exist = True
    for d in dirs:
        path = Path(d)
        if path.exists():
            print(f"✓ {d}/")
        else:
            print(f"❌ {d}/ - NOT FOUND")
            all_exist = False
    
    return all_exist


def main():
    print("=" * 70)
    print("Environment Verification")
    print("=" * 70)
    print()
    
    # Python version
    print("Python Version:")
    python_ok = check_python_version()
    print()
    
    # Dependencies
    print("Python Packages:")
    deps_ok, missing = check_dependencies()
    print()
    
    if not deps_ok:
        print("To install missing packages:")
        print("  pip install -r requirements.txt")
        print()
    
    # Kaggle credentials
    print("Kaggle API:")
    kaggle_ok = check_kaggle_credentials()
    print()
    
    # Directory structure
    print("Directory Structure:")
    dirs_ok = check_directories()
    print()
    
    # Summary
    print("=" * 70)
    if python_ok and deps_ok and dirs_ok:
        print("✓ Environment ready!")
        if not kaggle_ok:
            print("⚠️  Kaggle credentials not configured (optional for now)")
        print()
        print("Next steps:")
        print("  1. Configure Kaggle API (see SETUP.md)")
        print("  2. Run: python scripts/01_download_data.py")
    else:
        print("❌ Environment issues detected - see above")
        print()
        print("Setup instructions: SETUP.md")
    print("=" * 70)


if __name__ == "__main__":
    main()
