param(
    [Parameter(Mandatory=$true)]
    [string]$Text
)

Add-Type -AssemblyName "System.Runtime.WindowsRuntime"

$synth = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
$voice = $synth.AllVoices | Where-Object { $_.Language -eq "th-TH" } | Select-Object -First 1

if ($voice) {
    $synth.Voice = $voice
    Write-Host "Using Voice: $($voice.DisplayName)"
} else {
    Write-Warning "Thai OneCore voice not found."
    return
}

$streamTask = $synth.SynthesizeTextToStreamAsync($Text)
$stream = $streamTask.AsTask().Result

$player = New-Object Windows.Media.Playback.MediaPlayer
$player.Source = [Windows.Media.Playback.MediaSource]::CreateFromStream($stream, $stream.ContentType)
$player.Play()

Write-Host "Speaking..."
$waitSec = [math]::Max(5, $Text.Length / 5)
Start-Sleep -Seconds $waitSec
