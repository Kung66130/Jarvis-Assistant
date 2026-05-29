# jarvis_next.ps1
# Entry Point for Jarvis Next Stack
# Usage:
#   .\next\jarvis_next.ps1           -> Text mode (Whisper STT + Gemini 2.5 Flash)
#   .\next\jarvis_next.ps1 -Mode live -> Live mode (Gemini Live voice-to-voice)

param(
    [ValidateSet("text", "live")]
    [string]$Mode = "text"
)

$Python    = "C:\Users\kung6\AppData\Local\Programs\Python\Python312\python.exe"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RootDir   = Split-Path -Parent $ScriptDir

# Load .env
$EnvFile = Join-Path $RootDir ".env"
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match "^\s*([^#][^=]+)=(.+)$") {
            [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
}

Write-Host "=== Jarvis NEXT — Mode: $Mode ===" -ForegroundColor Cyan

if ($Mode -eq "live") {
    Write-Host "Starting Gemini Live Mode (Voice-to-Voice)..." -ForegroundColor Yellow
    & $Python "$ScriptDir\jarvis_live.py"
} else {
    Write-Host "Starting Text Mode (Whisper STT + Gemini 2.5 Flash)..." -ForegroundColor Yellow
    & $Python "$ScriptDir\jarvis_next_loop.py"
}
