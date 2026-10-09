@echo off
REM ImageEditor Launcher - double-click this file to run the editor
REM No PowerShell needed

REM Try pythonw (no console window)
REM Update these paths if your Python is in a different location

set PYTHONW=C:\Users\tc06h\AppData\Local\Programs\Python\Python312\pythonw.exe
set SCRIPT=C:\Users\tc06h\Documents\ImageEditor\main.py

REM Check if pythonw exists, fallback to python
if exist "%PYTHONW%" (
    start "" "%PYTHONW%" "%SCRIPT%"
) else (
    echo pythonw not found, trying python...
    python "%SCRIPT%"
    pause
)
