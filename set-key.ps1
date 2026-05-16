param(
    [string]$EnvPath = (Join-Path $PSScriptRoot ".env")
)

$ErrorActionPreference = "Stop"

$key = Read-Host "Paste GEMINI_API_KEY"
if (-not $key) {
    throw "GEMINI_API_KEY is required."
}

"GEMINI_API_KEY=$key" | Out-File -LiteralPath $EnvPath -Encoding utf8
Write-Host "Wrote GEMINI_API_KEY to $EnvPath" -ForegroundColor Green
