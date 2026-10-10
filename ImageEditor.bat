@echo off
title ImageEditor v8.0 Tier 8 ALL
echo ========================================
echo   ImageEditor v8.0 Tier 8 - 5626 lines
echo   SAFE - No SmartScreen - Python BAT
echo ========================================
python main.py
if %errorlevel% neq 0 (
  pip install -r requirements.txt
  python main.py
)
pause
