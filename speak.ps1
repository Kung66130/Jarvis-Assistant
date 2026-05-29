param(
    [Parameter(Mandatory = $true)][string]$Text,
    [string]$Voice = "niwat",
    [string]$Provider = "auto",
    [string]$Tone = "calm"
)

$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition

function Get-PythonCommand {
    $candidates = @(
        [PSCustomObject]@{ Command = "C:\Users\kung6\AppData\Local\Programs\Python\Python312\python.exe"; Args = @() },
        [PSCustomObject]@{ Command = "python"; Args = @() },
        [PSCustomObject]@{ Command = "py"; Args = @("-3.12") }
    )

    foreach ($candidate in $candidates) {
        $cmd = Get-Command $candidate.Command -ErrorAction SilentlyContinue
        if ($cmd) {
            return $candidate
        }
    }

    throw "Python runtime not found. Install Python or put python.exe on PATH."
}

$python = Get-PythonCommand

# Avoid mojibake when passing Thai text via argv (console codepage issues).
# Write to a UTF-8 temp file and let Python read it as UTF-8.
$tmp = Join-Path $env:TEMP ("jarvis_speak_{0}.txt" -f ([Guid]::NewGuid().ToString("N")))
try {
    Set-Content -LiteralPath $tmp -Value $Text -Encoding utf8

    $providerName = ($Provider | ForEach-Object { $_.ToLowerInvariant() })
    if ($providerName -notin @("auto", "edge", "sapi")) {
        Write-Warning "speak.ps1: Provider '$Provider' is not supported in this build; using auto."
        $providerName = "auto"
    }

    & $python.Command @($python.Args + "$PSScriptRoot\pro_speak.py" + "--file" + $tmp + "--voice" + $Voice + "--provider" + $providerName)
}
finally {
    Remove-Item -LiteralPath $tmp -ErrorAction SilentlyContinue
}
