@echo off
setlocal

REM Keep this file ASCII-only for compatibility with cmd.exe encodings.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$t = Read-Host 'Enter text to speak'; & '%~dp0speak.ps1' -Text $t"
pause
