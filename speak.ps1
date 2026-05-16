param(
    [string]$Text = "Hello Boss",
    [string]$Provider = "edge",
    [string]$Tone = "friendly",
    [string]$Voice = "niwat",
    [string]$Rate = "",
    [string]$Pitch = "",
    [switch]$Precache
)

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

$scriptPath = Join-Path $PSScriptRoot "pro_speak.py"
if (-not (Test-Path $scriptPath)) {
    throw "Error: File pro_speak.py not found"
}

$python = Get-PythonCommand
$arguments = @()
$arguments += $python.Args
$arguments += $scriptPath
$arguments += "--provider"
$arguments += $Provider
$arguments += "--tone"
$arguments += $Tone
$arguments += "--voice"
$arguments += $Voice

if ($Rate) {
    $arguments += "--rate"
    $arguments += $Rate
}

if ($Pitch) {
    $arguments += "--pitch"
    $arguments += $Pitch
}

if ($Precache) {
    $arguments += "--cache-only"
}

$arguments += "--"
$arguments += $Text

& $python.Command @arguments
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
