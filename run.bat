@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run scripts\setup.ps1 in PowerShell first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" main.py
if errorlevel 1 pause
