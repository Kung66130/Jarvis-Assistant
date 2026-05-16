import argparse
import asyncio
import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from jarvis_runtime import get_env_value

try:
    import edge_tts
except ImportError:
    edge_tts = None


VOICES = {
    "niwat": "th-TH-NiwatNeural",
    "premwadee": "th-TH-PremwadeeNeural",
}
DEFAULT_VOICE = "niwat"
DEFAULT_PROVIDER = "edge"
CACHE_DIR = os.path.join(os.path.dirname(__file__), "voice_cache")
STATE_FILE = os.path.join(os.path.dirname(__file__), "state.txt")

STYLE_PRESETS = {
    "neutral": {"voice": "niwat", "rate": "+0%", "pitch": "+0Hz"},
    "calm": {"voice": "niwat", "rate": "-12%", "pitch": "-4Hz"},
    "friendly": {"voice": "niwat", "rate": "+4%", "pitch": "+4Hz"},
    "cheerful": {"voice": "premwadee", "rate": "+12%", "pitch": "+12Hz"},
    "serious": {"voice": "niwat", "rate": "-8%", "pitch": "-6Hz"},
    "urgent": {"voice": "niwat", "rate": "+10%", "pitch": "+6Hz"},
}

os.makedirs(CACHE_DIR, exist_ok=True)


def write_state(state: str) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as state_file:
        state_file.write(state)


def play_mp3(path: str) -> bool:
    write_state("SPEAKING")
    resolved_path = os.path.abspath(path)
    ps_script = (
        "Add-Type -AssemblyName PresentationCore; "
        "$p = New-Object System.Windows.Media.MediaPlayer; "
        f"$p.Open('{resolved_path}'); "
        "$i = 0; while ($p.NaturalDuration.HasTimeSpan -eq $false -and $i -lt 100) { Start-Sleep -m 20; $i++ }; "
        "$p.Play(); "
        "if ($p.NaturalDuration.HasTimeSpan) { Start-Sleep -s ($p.NaturalDuration.TimeSpan.TotalSeconds + 0.5) } else { Start-Sleep -s 5 }"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
        check=False,
    )
    write_state("IDLE")
    return True


def play_audio_file(path: str) -> bool:
    # MediaPlayer can handle both mp3 and wav.
    return play_mp3(path)


@dataclass
class SpeechRequest:
    text: str
    provider: str = DEFAULT_PROVIDER
    tone: str = "friendly"
    voice: str = DEFAULT_VOICE
    rate: str = "+0%"
    pitch: str = "+0Hz"
    cache_only: bool = False


class BaseTTSProvider:
    async def synthesize(self, request: SpeechRequest, cache_path: str) -> None:
        raise NotImplementedError


class EdgeTTSProvider(BaseTTSProvider):
    async def synthesize(self, request: SpeechRequest, cache_path: str) -> None:
        if edge_tts is None:
            raise RuntimeError(
                "Missing dependency: edge_tts. Install project dependencies before running TTS."
            )

        voice_name = VOICES.get(request.voice, VOICES[DEFAULT_VOICE])
        communicate = edge_tts.Communicate(
            request.text,
            voice_name,
            rate=request.rate,
            pitch=request.pitch,
        )
        await communicate.save(cache_path)


class SapiTTSProvider(BaseTTSProvider):
    async def synthesize(self, request: SpeechRequest, cache_path: str) -> None:
        # Offline Windows SAPI via PowerShell; output to WAV.
        # Use a UTF-8 temp file for the input text to avoid encoding/escaping issues.
        out_path = os.path.abspath(cache_path).replace("'", "''")

        def normalize_for_sapi(text: str) -> str:
            # English-only SAPI voices will read Thai with an accent anyway, but we can at least
            # reduce "computer-y" tokens that tend to trigger long English spell-outs.
            text = text.replace("\\", " / ")
            text = text.replace(":", " : ")
            text = text.replace("_", " ")
            return text

        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8") as temp_file:
            temp_file.write(normalize_for_sapi(request.text))
            text_path = temp_file.name

        text_path_escaped = os.path.abspath(text_path).replace("'", "''")

        rate = 0
        try:
            rate_str = str(request.rate or "").strip().replace("%", "")
            if rate_str:
                rate = int(round(float(rate_str) / 10.0))
                rate = max(-10, min(10, rate))
        except Exception:
            rate = 0

        ps = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$s.Rate = {rate}; "
            f"$t = Get-Content -LiteralPath '{text_path_escaped}' -Raw -Encoding UTF8; "
            f"$s.SetOutputToWaveFile('{out_path}'); "
            "$s.Speak($t); "
            "$s.Dispose(); "
            f"Remove-Item -LiteralPath '{text_path_escaped}' -Force -ErrorAction SilentlyContinue;"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
            check=True,
        )


class GoogleTTSProvider(BaseTTSProvider):
    async def synthesize(self, request: SpeechRequest, cache_path: str) -> None:
        api_key = get_env_value("GOOGLE_TTS_API_KEY") or get_env_value("GOOGLE_CLOUD_TTS_API_KEY")
        if not api_key:
            raise RuntimeError("Missing GOOGLE_TTS_API_KEY for provider=google.")

        voice_name = (get_env_value("GOOGLE_TTS_VOICE_NAME") or "").strip()
        language_code = (get_env_value("GOOGLE_TTS_LANGUAGE") or "th-TH").strip() or "th-TH"

        # Map "+10%" to speakingRate ~ 1.10. Google supports 0.25..4.0.
        speaking_rate = 1.0
        try:
            rate_str = str(request.rate or "").strip().replace("%", "")
            if rate_str:
                speaking_rate = 1.0 + (float(rate_str) / 100.0)
                speaking_rate = max(0.25, min(4.0, speaking_rate))
        except Exception:
            speaking_rate = 1.0

        # Google pitch is in semitones [-20..20]. We treat our "+4Hz" as a best-effort numeric.
        pitch = 0.0
        try:
            pitch_str = str(request.pitch or "").strip().lower().replace("hz", "")
            if pitch_str:
                pitch = float(pitch_str)
                pitch = max(-20.0, min(20.0, pitch))
        except Exception:
            pitch = 0.0

        voice: dict[str, object] = {"languageCode": language_code}
        if voice_name:
            voice["name"] = voice_name

        payload = {
            "input": {"text": request.text},
            "voice": voice,
            "audioConfig": {
                "audioEncoding": "MP3",
                "speakingRate": speaking_rate,
                "pitch": pitch,
            },
        }

        endpoint = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={api_key}"
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace") if exc.fp else str(exc)
            raise RuntimeError(f"Google TTS HTTP {exc.code}: {detail}") from exc
        except Exception as exc:
            raise RuntimeError(f"Google TTS request failed: {exc}") from exc

        result = json.loads(body.decode("utf-8"))
        audio_content = result.get("audioContent")
        if not audio_content:
            raise RuntimeError("Google TTS response missing audioContent.")

        audio_bytes = base64.b64decode(audio_content)
        with open(cache_path, "wb") as audio_file:
            audio_file.write(audio_bytes)


PROVIDERS: dict[str, BaseTTSProvider] = {
    "edge": EdgeTTSProvider(),
    "google": GoogleTTSProvider(),
    "sapi": SapiTTSProvider(),
}


def normalize_request(request: SpeechRequest) -> SpeechRequest:
    tone = (request.tone or "friendly").lower()
    preset = STYLE_PRESETS.get(tone, STYLE_PRESETS["friendly"])

    voice = (request.voice or preset["voice"]).lower()
    if voice not in VOICES:
        voice = preset["voice"]

    rate = request.rate or preset["rate"]
    pitch = request.pitch or preset["pitch"]

    return SpeechRequest(
        text=request.text,
        provider=(request.provider or DEFAULT_PROVIDER).lower(),
        tone=tone,
        voice=voice,
        rate=rate,
        pitch=pitch,
        cache_only=request.cache_only,
    )


def get_cache_path(request: SpeechRequest) -> str:
    cache_key = "|".join(
        [
            request.provider,
            request.tone,
            request.voice,
            request.rate,
            request.pitch,
            request.text,
        ]
    )
    text_hash = hashlib.md5(cache_key.encode("utf-8")).hexdigest()
    ext = "mp3" if request.provider in {"edge", "google"} else "wav"
    return os.path.join(CACHE_DIR, f"{text_hash}.{ext}")


async def synthesize_if_needed(request: SpeechRequest, cache_path: str) -> None:
    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
        return

    provider = PROVIDERS.get(request.provider)
    if provider is None:
        raise ValueError(f"Unsupported TTS provider: {request.provider}")

    last_error = None
    for _ in range(3):
        try:
            await provider.synthesize(request, cache_path)
            if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
                return
        except Exception as exc:
            last_error = exc
            time.sleep(1)

    raise RuntimeError(f"Unable to synthesize speech after multiple attempts: {last_error}")


async def speak(request: SpeechRequest) -> None:
    normalized = normalize_request(request)
    cache_path = get_cache_path(normalized)
    await synthesize_if_needed(normalized, cache_path)

    if not normalized.cache_only:
        play_audio_file(cache_path)


def parse_args() -> SpeechRequest:
    parser = argparse.ArgumentParser()
    parser.add_argument("text", nargs="*", help="Text to speak")
    parser.add_argument("--provider", default=DEFAULT_PROVIDER)
    parser.add_argument("--tone", default="friendly")
    parser.add_argument("--voice", default=DEFAULT_VOICE)
    parser.add_argument("--rate", default="")
    parser.add_argument("--pitch", default="")
    parser.add_argument("--cache-only", action="store_true")
    args = parser.parse_args()

    text = " ".join(args.text).strip() or "สวัสดีครับบอส ผมพร้อมช่วยงานแล้วครับ"
    return SpeechRequest(
        text=text,
        provider=args.provider,
        tone=args.tone,
        voice=args.voice,
        rate=args.rate,
        pitch=args.pitch,
        cache_only=args.cache_only,
    )


if __name__ == "__main__":
    asyncio.run(speak(parse_args()))
