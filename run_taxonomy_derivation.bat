@echo off
echo ============================================================
echo Step 1: Sampling AmazonHelp threads
echo ============================================================
python scripts\04_sample_for_taxonomy.py --brand AmazonHelp --sample-size 150

echo.
echo ============================================================
echo Step 2: Proposing taxonomy from samples
echo ============================================================
python scripts\05_propose_taxonomy.py

echo.
echo ============================================================
echo Done! Check outputs\proposed_taxonomy.json
echo ============================================================
pause
