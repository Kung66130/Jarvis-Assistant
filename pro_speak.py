import os
import sys
import argparse
import hashlib
import asyncio
import subprocess
import threading
import tempfile

from jarvis_runtime import get_default_tts_provider

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "voice_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

VOICE_MAP = {
    "niwat": "th-TH-NiwatNeural",
    "premwadee": "th-TH-PremwadeeNeural",
    "achara": "th-TH-AcharaNeural",
}

async def synthesize(text: str, voice: str, output_path: str):
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)


def synthesize_sapi(text: str, output_path: str) -> None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8") as temp_file:
        temp_file.write(text)
        text_path = temp_file.name

    out_path = os.path.abspath(output_path).replace("'", "''")
    text_path_escaped = os.path.abspath(text_path).replace("'", "''")
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$voices = $s.GetInstalledVoices(); "
        "$thai = $voices | Where-Object { $_.VoiceInfo.Culture.Name -like 'th-*' } | Select-Object -First 1; "
        "if ($thai) { $s.SelectVoice($thai.VoiceInfo.Name) }; "
        f"$text = Get-Content -LiteralPath '{text_path_escaped}' -Raw -Encoding UTF8; "
        f"$s.SetOutputToWaveFile('{out_path}'); "
        "$s.Speak($text); "
        "$s.Dispose(); "
        f"Remove-Item -LiteralPath '{text_path_escaped}' -Force -ErrorAction SilentlyContinue;"
    )
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def resolve_voice(voice: str) -> str:
    return VOICE_MAP.get((voice or "").lower(), "th-TH-NiwatNeural")


def build_provider_chain(provider: str, *, preferred_provider: str | None = None) -> list[str]:
    provider = (provider or "auto").lower()
    preferred = (preferred_provider or get_default_tts_provider()).lower()

    if provider != "auto":
        return [provider]

    if preferred == "edge":
        return ["edge", "sapi"]
    return ["sapi", "edge"]


def get_cache_path(text: str, voice: str, provider: str) -> str:
    voice_name = resolve_voice(voice)
    digest = hashlib.md5(f"{provider}|{voice_name}|{text}".encode("utf-8")).hexdigest()
    extension = "wav" if provider == "sapi" else "mp3"
    return os.path.join(CACHE_DIR, f"{digest}.{extension}")


def synthesize_to_cache(text: str, voice: str, provider: str) -> str:
    output_path = get_cache_path(text, voice, provider)
    if os.path.exists(output_path):
        return output_path

    if provider == "sapi":
        print("[SAPI] Synthesizing...", file=sys.stderr)
        synthesize_sapi(text, output_path)
        return output_path

    print("[Edge TTS] Synthesizing...", file=sys.stderr)
    asyncio.run(synthesize(text, resolve_voice(voice), output_path))
    return output_path


def ensure_audio_cached(text: str, voice: str, provider: str = "auto") -> str:
    providers = build_provider_chain(provider)
    last_error: Exception | None = None

    for current_provider in providers:
        try:
            return synthesize_to_cache(text, voice, current_provider)
        except Exception as exc:
            last_error = exc
            print(f"[TTS] Provider {current_provider} failed: {exc}", file=sys.stderr)

    raise RuntimeError(f"Unable to synthesize speech: {last_error}")


def start_audio_playback(audio_path: str) -> subprocess.Popen | None:
    if not os.path.exists(audio_path):
        return None
    return subprocess.Popen(
        ["ffplay", "-nodisp", "-autoexit", "-hide_banner", "-loglevel", "quiet", audio_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def wait_for_playback(
    playback_process: subprocess.Popen | None,
    *,
    stop_event: threading.Event | None = None,
    poll_interval: float = 0.05,
) -> bool:
    if playback_process is None:
        return False

    while playback_process.poll() is None:
        if stop_event and stop_event.wait(poll_interval):
            playback_process.terminate()
            try:
                playback_process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                playback_process.kill()
                playback_process.wait(timeout=1)
            return False
        if not stop_event:
            try:
                playback_process.wait(timeout=poll_interval)
            except subprocess.TimeoutExpired:
                continue

    return playback_process.returncode == 0


def play_audio(audio_path: str, *, stop_event: threading.Event | None = None) -> bool:
    playback_process = start_audio_playback(audio_path)
    try:
        return wait_for_playback(playback_process, stop_event=stop_event)
    except Exception as exc:
        print(f"Playback error: {exc}", file=sys.stderr)
        return False


def speak_text(
    text: str,
    voice: str = "niwat",
    *,
    provider: str = "auto",
    stop_event: threading.Event | None = None,
) -> bool:
    if not text:
        return False
    audio_path = ensure_audio_cached(text, voice, provider=provider)
    print(f"[FFplay] Playing: {audio_path}", file=sys.stderr)
    return play_audio(audio_path, stop_event=stop_event)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("text", nargs="*", default=[])
    parser.add_argument("--file", help="Path to text file to speak")
    parser.add_argument("--preset", help="Use a built-in text preset (e.g., 'greeting')")
    parser.add_argument("--voice", default="niwat")
    parser.add_argument("--provider", default="auto", choices=["auto", "edge", "sapi"])
    args = parser.parse_args()

    if args.preset == "greeting":
        text = "ระบบจาร์วิสออนไลน์ พร้อมรับคำสั่งครับบอส"
    elif args.file and os.path.exists(args.file):
        with open(args.file, "r", encoding="utf-8") as f:
            text = f.read().strip().lstrip('\ufeff')
    else:
        text = " ".join(args.text).strip().lstrip('\ufeff')
    if not text:
        return

    speak_text(text, args.voice, provider=args.provider)

if __name__ == "__main__":
    main()
