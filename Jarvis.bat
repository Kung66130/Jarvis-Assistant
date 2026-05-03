@echo off
setlocal

REM ASCII-only file for cmd.exe compatibility.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0jarvis.ps1"
