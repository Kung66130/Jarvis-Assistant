param(
    [string]$Text = "Hello Boss"
)

$scriptPath = "$PSScriptRoot\pro_speak.py"

if (Test-Path $scriptPath) {
    py -3.12 $scriptPath $Text
} else {
    Write-Error "Error: File pro_speak.py not found"
}
