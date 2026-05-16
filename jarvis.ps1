[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8

function Get-PythonCommand {
    $venvPython = Join-Path $PSScriptRoot ".venv\\Scripts\\python.exe"
    if (Test-Path $venvPython) {
        return [PSCustomObject]@{ Command = $venvPython; Args = @() }
    }

    $candidates = @(
        [PSCustomObject]@{ Command = "python"; Args = @() },
        [PSCustomObject]@{ Command = "py"; Args = @() }
    )

    foreach ($candidate in $candidates) {
        $cmd = Get-Command $candidate.Command -ErrorAction SilentlyContinue
        if ($cmd) {
            return $candidate
        }
    }

    throw "Python runtime not found. Install Python or put python.exe on PATH."
}

function Invoke-PythonScript {
    param(
        [Parameter(Mandatory = $true)][string]$ScriptPath,
        [string[]]$ScriptArgs = @()
    )

    $python = Get-PythonCommand
    $arguments = @()
    $arguments += $python.Args
    $arguments += $ScriptPath
    $arguments += $ScriptArgs

    & $python.Command @arguments
}

# Load Keywords and Messages from JSON
$keywordsPath = Join-Path $PSScriptRoot "keywords.json"
if (Test-Path $keywordsPath) {
    $keywords = Get-Content $keywordsPath -Raw | ConvertFrom-Json
} else {
    $keywords = [PSCustomObject]@{
        stop_keywords = @("exit", "quit")
        welcome_message = "ระบบจาวิสพร้อมใช้งานครับบอส"
        stop_message = "รับทราบครับบอส แล้วพบกันใหม่ครับ"
        error_message = "ขออภัยครับบอส ระบบกำลังมีปัญหาชั่วคราว"
    }
}

# --- SINGLE INSTANCE CHECK ---
$currentProcess = [System.Diagnostics.Process]::GetCurrentProcess()
$otherInstances = Get-Process -Name powershell, pwsh -ErrorAction SilentlyContinue | Where-Object {
    $_.Id -ne $currentProcess.Id -and $_.CommandLine -like "*jarvis.ps1*"
}

if ($otherInstances) {
    Write-Host "WARNING: Another instance of Jarvis is already running!" -ForegroundColor Red
    Write-Host "Please close the existing one before starting a new session." -ForegroundColor Yellow
    Start-Sleep -Seconds 3
    exit
}
# -----------------------------

function Invoke-Speak {
    param(
        [Parameter(Mandatory = $true)][string]$Text,
        [string]$Tone = "friendly",
        [string]$Voice = "niwat",
        [string]$Rate = "",
        [string]$Pitch = "",
        [switch]$Precache
    )

    $speakArgs = @{
        Text = $Text
        Tone = $Tone
        Voice = $Voice
    }

    if ($Rate) { $speakArgs.Rate = $Rate }
    if ($Pitch) { $speakArgs.Pitch = $Pitch }
    if ($Precache) { $speakArgs.Precache = $true }

    # Prefer edge, then Google TTS (if configured), then Desktop SAPI.
    & "$PSScriptRoot\speak.ps1" @speakArgs -Provider "edge"
    if ($LASTEXITCODE -ne 0) {
        & "$PSScriptRoot\speak.ps1" @speakArgs -Provider "google"
    }
    if ($LASTEXITCODE -ne 0) {
        & "$PSScriptRoot\speak.ps1" @speakArgs -Provider "sapi"
    }
}

function Warm-CommonSpeechCache {
    $commonPhrases = @(
        @{ Text = $keywords.welcome_message; Tone = "friendly"; Voice = "niwat" },
        @{ Text = $keywords.stop_message; Tone = "calm"; Voice = "niwat" },
        @{ Text = $keywords.error_message; Tone = "calm"; Voice = "niwat" },
        @{ Text = "รับทราบครับบอส"; Tone = "serious"; Voice = "niwat" }
    )

    foreach ($phrase in $commonPhrases) {
        try {
            Invoke-Speak -Text $phrase.Text -Tone $phrase.Tone -Voice $phrase.Voice -Precache
        } catch {
        }
    }
}

function Convert-AiPayload {
    param([string]$RawOutput)

    try {
        return $RawOutput | ConvertFrom-Json -ErrorAction Stop
    } catch {
        return [PSCustomObject]@{
            reply_text = $RawOutput
            speech = [PSCustomObject]@{
                tone = "friendly"
                voice = "niwat"
                rate = "+0%"
                pitch = "+0Hz"
            }
        }
    }
}

function Stop-Jarvis {
    Write-Host "Cleaning up background processes..." -ForegroundColor Yellow

    $uiProcesses = Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*ui_qt.py*" }
    foreach ($p in $uiProcesses) {
        Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
    }

    $pingProcesses = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*curl*raspberrykung*" }
    foreach ($p in $pingProcesses) {
        Write-Host "Stopping keep-alive ping (PID: $($p.Id))..." -ForegroundColor Gray
        Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
    }

    $mcpProcesses = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*ollama-mcp*" }
    foreach ($p in $mcpProcesses) {
        Write-Host "Stopping redundant MCP server (PID: $($p.Id))..." -ForegroundColor Gray
        Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
    }

    "" | Out-File "$PSScriptRoot\state.txt" -Encoding utf8
    exit
}

# --- UI STARTUP LOGIC ---
Write-Host "Ensuring clean UI state..." -ForegroundColor Gray
$oldUiProcesses = Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*ui_qt.py*" }
foreach ($p in $oldUiProcesses) {
    Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Milliseconds 500

Write-Host "Initializing Holographic UI..." -ForegroundColor Cyan
$pythonForUi = Get-PythonCommand
$uiArgs = @()
$uiArgs += $pythonForUi.Args
$uiArgs += "`"$PSScriptRoot\ui_qt.py`""
$proc = Start-Process $pythonForUi.Command -ArgumentList $uiArgs -WindowStyle Hidden -PassThru
$uiPid = $proc.Id
# ------------------------

Warm-CommonSpeechCache

Write-Host "Jarvis Central System is online." -ForegroundColor Cyan
Invoke-Speak -Text $keywords.welcome_message -Tone "friendly" -Voice "niwat"

try {
    while ($true) {
        if (-not (Get-Process -Id $uiPid -ErrorAction SilentlyContinue)) {
            Write-Host "UI closed by user. Shutting down system." -ForegroundColor Red
            break
        }

        "AWAITING" | Out-File "$PSScriptRoot\state.txt" -Encoding utf8
        Write-Host "Ready! Say 'Jarvis' to wake me up..." -ForegroundColor Gray

        $voiceOutput = Invoke-PythonScript -ScriptPath "$PSScriptRoot\listen.py"
        $voiceOutputStr = $voiceOutput -join "`n"

        if ($voiceOutputStr -and ($voiceOutputStr -match "RESULT:(.*)")) {
            $recognizedText = $matches[1].Trim()
            if ($recognizedText -eq "NONE" -or $recognizedText -eq "") { continue }

            Write-Host "Boss: $recognizedText" -ForegroundColor Green

            $isStop = $false
            foreach ($sk in $keywords.stop_keywords) {
                if ($recognizedText -match $sk) {
                    $isStop = $true
                    break
                }
            }

            if ($isStop) {
                Invoke-Speak -Text $keywords.stop_message -Tone "calm" -Voice "niwat"
                break
            }

            "THINKING" | Out-File "$PSScriptRoot\state.txt" -Encoding utf8
            Write-Host "Jarvis is thinking..." -ForegroundColor Yellow
            $aiResponse = Invoke-PythonScript -ScriptPath "$PSScriptRoot\brain.py" -ScriptArgs @($recognizedText) 2>$null
            $aiResponseStr = $aiResponse -join "`n"

            if ($aiResponseStr) {
                $payload = Convert-AiPayload -RawOutput $aiResponseStr
                $replyText = $payload.reply_text
                $speech = $payload.speech

                if (-not $replyText) {
                    $replyText = $keywords.error_message
                    $speech = [PSCustomObject]@{
                        tone = "calm"
                        voice = "niwat"
                        rate = "-10%"
                        pitch = "-4Hz"
                    }
                }

                Write-Host "Jarvis: $replyText" -ForegroundColor Cyan
                Invoke-Speak -Text $replyText -Tone $speech.tone -Voice $speech.voice -Rate $speech.rate -Pitch $speech.pitch
            } else {
                Invoke-Speak -Text $keywords.error_message -Tone "calm" -Voice "niwat"
            }
        }
    }
}
finally {
    Stop-Jarvis
}
