@echo off
title Jarvis - Full System Launcher
echo ===================================================
echo   Jarvis Full System Launcher
echo ===================================================

REM 1. Start Telegram Remote Bot (bot.py with venv)
echo [+] Starting Telegram Remote Bot...
start "Jarvis Telegram Bot" /min cmd /c "C:\Project\Telegram-Remote-Approver\venv\Scripts\python.exe -u C:\Project\Telegram-Remote-Approver\bot.py"

REM 2. Brief pause to let bot initialize first
timeout /t 2 /nobreak >nul

REM 3. Start Jarvis Main Brain + Voice Loop
echo [+] Starting Jarvis Brain...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0jarvis.ps1"
