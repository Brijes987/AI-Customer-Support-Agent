@echo off
echo Testing thread reconstruction with manifest...
echo.
python scripts\02_reconstruct_threads.py --limit 100
echo.
echo Test complete!
pause
