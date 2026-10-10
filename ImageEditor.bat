@echo off
title ImageEditor v8.0 Tier 8
echo ========================================
echo   ImageEditor v8.0 Tier 8 ALL - 5626 lines
echo   SAFE - No SmartScreen!
echo ========================================
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found!
    pause
    exit /b
)
if not exist main.py (
    echo ERROR: main.py not found!
    pause
    exit /b
)
echo Starting...
python main.py
if %errorlevel% neq 0 (
    echo Installing requirements...
    pip install -r requirements.txt
    python main.py
)
pause