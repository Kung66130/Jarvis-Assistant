$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

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
& $python.Command @($python.Args + "$PSScriptRoot\jarvis_loop.py")
