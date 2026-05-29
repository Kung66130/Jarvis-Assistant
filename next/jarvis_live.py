"""
jarvis_live.py — Jarvis Live Mode (Voice-to-Voice)
ใช้ Gemini Live API — พูดเข้า → AI ตอบ → พูดออก ไม่ต้องผ่าน STT/TTS แยก
Latency ต่ำมาก (sub-second end-to-end)

รัน: python jarvis_live.py
หยุด: Ctrl+C หรือพูด "ปิดระบบ"
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys
from pathlib import Path

import pyaudio

# Parent directory
_PARENT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PARENT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from jarvis_runtime import get_env_value

try:
    from google import genai
    from google.genai import types as gen_types
except ImportError:
    print("กรุณาติดตั้ง google-genai ก่อนครับ: pip install google-genai", file=sys.stderr)
    sys.exit(1)

# ── Audio Config ───────────────────────────────────────────────────────────
FORMAT      = pyaudio.paInt16
CHANNELS    = 1
SEND_RATE   = 16000   # mic  → Gemini (PCM 16kHz)
RECV_RATE   = 24000   # Gemini → speaker (PCM 24kHz)
CHUNK       = 1024

# ── Model Config ───────────────────────────────────────────────────────────
import json as _json
_CFG_PATH = Path(__file__).resolve().parent / "config_next.json"
with open(_CFG_PATH, encoding="utf-8") as _f:
    _CFG = _json.load(_f)

LIVE_MODEL = _CFG.get("live_model", "gemini-2.0-flash-live-001")

SYSTEM_PROMPT = """คุณคือ Jarvis ผู้ช่วย AI ของ "บอส"

กติกา:
- ตอบภาษาไทยเป็นหลัก สั้น กระชับ เป็นธรรมชาติ
- ห้ามตอบยาวเกินจำเป็น ไม่ต้องบอก "ผมคือ AI"
- ถ้าไม่เข้าใจให้ถามซ้ำสั้น ๆ
- พูดเหมือนผู้ช่วยส่วนตัวที่ไว้วางใจได้"""


# ── Live Session ───────────────────────────────────────────────────────────
async def run_live_session() -> None:
    api_key = get_env_value("GEMINI_API_KEY", allow_legacy_config=True)
    if not api_key:
        raise RuntimeError("ไม่พบ GEMINI_API_KEY กรุณาตั้งค่าใน .env ก่อนครับ")

    client = genai.Client(api_key=api_key)

    config = gen_types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=gen_types.Content(
            parts=[gen_types.Part.from_text(SYSTEM_PROMPT)]
        ),
        speech_config=gen_types.SpeechConfig(
            voice_config=gen_types.VoiceConfig(
                prebuilt_voice_config=gen_types.PrebuiltVoiceConfig(
                    voice_name="Charon"  # Male voice — เปลี่ยนได้: Puck, Charon, Kore, Fenrir, Aoede
                )
            )
        ),
    )

    pya = pyaudio.PyAudio()
    stop_event = asyncio.Event()
    audio_send_q: asyncio.Queue[bytes] = asyncio.Queue(maxsize=50)

    # Open mic input stream
    in_stream = pya.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=SEND_RATE,
        input=True,
        frames_per_buffer=CHUNK,
    )

    # Open speaker output stream
    out_stream = pya.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RECV_RATE,
        output=True,
        frames_per_buffer=CHUNK,
    )

    print("\n" + "=" * 50)
    print("  Jarvis LIVE Mode — พูดได้เลยครับบอส")
    print("  (Ctrl+C เพื่อหยุด)")
    print("=" * 50 + "\n")

    async with client.aio.live.connect(model=LIVE_MODEL, config=config) as session:

        async def capture_mic() -> None:
            """อ่าน audio จาก mic → ใส่ queue"""
            loop = asyncio.get_event_loop()
            while not stop_event.is_set():
                try:
                    data = await loop.run_in_executor(
                        None,
                        lambda: in_stream.read(CHUNK, exception_on_overflow=False),
                    )
                    await audio_send_q.put(data)
                except Exception as exc:
                    print(f"[Mic] Error: {exc}", file=sys.stderr)
                    break

        async def send_to_gemini() -> None:
            """ส่ง audio chunks ไปยัง Gemini Live"""
            while not stop_event.is_set():
                try:
                    chunk = await asyncio.wait_for(audio_send_q.get(), timeout=1.0)
                    await session.send(
                        input=gen_types.LiveClientRealtimeInput(
                            media_chunks=[
                                gen_types.Blob(
                                    data=chunk,
                                    mime_type=f"audio/pcm;rate={SEND_RATE}",
                                )
                            ]
                        )
                    )
                except asyncio.TimeoutError:
                    continue
                except Exception as exc:
                    print(f"[Send] Error: {exc}", file=sys.stderr)
                    break

        async def receive_and_play() -> None:
            """รับ audio จาก Gemini → เล่นออก speaker"""
            loop = asyncio.get_event_loop()
            async for response in session.receive():
                if stop_event.is_set():
                    break

                # เล่น audio
                if response.data:
                    await loop.run_in_executor(
                        None, lambda d=response.data: out_stream.write(d)
                    )

                # Print text transcript ถ้ามี
                if hasattr(response, "text") and response.text:
                    print(f"Jarvis: {response.text}", flush=True)

                # ตรวจสอบ tool call ถ้า Gemini Live ส่งมา
                if hasattr(response, "tool_call") and response.tool_call:
                    print(f"[Tool] {response.tool_call}", file=sys.stderr)

        try:
            await asyncio.gather(
                capture_mic(),
                send_to_gemini(),
                receive_and_play(),
            )
        finally:
            stop_event.set()
            in_stream.stop_stream()
            in_stream.close()
            out_stream.stop_stream()
            out_stream.close()
            pya.terminate()
            print("\nJarvis Live ปิดแล้วครับ", flush=True)


# ── Entry Point ────────────────────────────────────────────────────────────
def main() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def _sigint(_sig, _frame) -> None:
        print("\n\nกำลังปิด Jarvis Live...", flush=True)
        for task in asyncio.all_tasks(loop):
            task.cancel()
        loop.stop()

    signal.signal(signal.SIGINT, _sigint)

    try:
        loop.run_until_complete(run_live_session())
    except (RuntimeError, asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:
            pass
        loop.close()


if __name__ == "__main__":
    main()
