"""
jarvis_next_loop.py — Main Loop สำหรับ Jarvis Next Stack
ใช้: brain_next (Gemini 2.5 Flash + FC) + listen_next (Whisper STT)
Reuse: pro_speak, speech_controller, agent_worker จาก parent
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

# Setup paths
_HERE   = Path(__file__).resolve().parent
_PARENT = _HERE.parent
sys.path.insert(0, str(_PARENT))
sys.path.insert(0, str(_HERE))

# ── New modules (next/) ────────────────────────────────────────────────────
from brain_next import (
    fallback_response,
    get_ai_response,
    stream_ai_reply_text,
)
from listen_next import (
    detect_interrupt,
    find_input_device,
    recognize_command,
    wait_for_wake_activity,
)

# ── Reuse from parent (ไม่ duplicate) ─────────────────────────────────────
from speech_controller import SegmentSpeaker
from voice_stream import split_for_speech

APP_DIR = _PARENT


def print_status(prefix: str, text: str) -> None:
    try:
        print(f"{prefix}{text}", flush=True)
    except Exception:
        try:
            with open(APP_DIR / "jarvis_runtime.log", "a", encoding="utf-8") as f:
                f.write(f"{prefix}{text}\n")
        except Exception:
            pass


def start_agent_worker(action: dict) -> None:
    worker_path = APP_DIR / "agent_worker.py"
    if not worker_path.exists():
        print_status(">> ", f"agent_worker.py ไม่พบ: {worker_path}")
        return
    subprocess.Popen(
        [sys.executable, str(worker_path), json.dumps(action, ensure_ascii=False)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def speak_text_now(text: str, voice: str = "niwat") -> None:
    speaker = SegmentSpeaker(voice=voice)
    speaker.extend(split_for_speech(text, max_chars=70))
    speaker.finish()
    speaker.join()


def stream_and_speak_reply(command: str, device_index: int | None):
    """
    Streaming: เริ่มพูดทันทีที่ได้ segment แรก
    พร้อมกับดึง full response (รวม action) ใน background
    """
    speaker = SegmentSpeaker()
    stream_done      = threading.Event()
    full_done        = threading.Event()
    speaker_finalized = False
    payload_box: dict = {}
    emitted_segments: list[str] = []
    interrupted_command: str | None = None

    def stream_worker() -> None:
        try:
            for segment in stream_ai_reply_text(command):
                if speaker.stop_event().is_set():
                    return
                emitted_segments.append(segment)
                speaker.enqueue(segment)
        except Exception as exc:
            print_status(">> Stream error: ", str(exc))
        finally:
            stream_done.set()

    def full_worker() -> None:
        try:
            payload_box["payload"] = get_ai_response(command)
        except Exception as exc:
            payload_box["payload"] = fallback_response(command)
            payload_box["error"] = exc
        finally:
            full_done.set()

    threading.Thread(target=stream_worker, daemon=True).start()
    threading.Thread(target=full_worker, daemon=True).start()

    while True:
        payload = payload_box.get("payload")
        if isinstance(payload, dict):
            speech = payload.get("speech", {})
            speaker.set_voice(str(speech.get("voice") or "niwat"))
            if stream_done.is_set() and not speaker_finalized:
                if not emitted_segments:
                    speaker.extend(
                        split_for_speech(
                            str(payload.get("reply_text") or ""), max_chars=70
                        )
                    )
                speaker.finish()
                speaker_finalized = True

        if speaker.is_busy() and detect_interrupt(device_index):
            speaker.cancel()
            try:
                interrupted_command = recognize_command(device_index)
            except Exception:
                interrupted_command = None
            break

        if full_done.is_set() and stream_done.is_set() and not speaker.is_busy():
            break

        time.sleep(0.1)

    speaker.join()
    return interrupted_command, payload_box.get("payload")


def main() -> None:
    device_index = find_input_device()
    if device_index is None:
        print_status(">> ", "ไม่พบ mic ที่กำหนด ใช้ default device")

    print_status(">> ", "--- Jarvis NEXT (Gemini 2.5 Flash + Whisper) ---")
    speak_text_now("ระบบจาร์วิส Next ออนไลน์แล้วครับบอส")

    pending_command: str | None = None
    while True:
        if pending_command:
            command = pending_command
            pending_command = None
        else:
            wake_result = wait_for_wake_activity(device_index)
            if wake_result and wake_result.startswith("AGENT_REPORT:"):
                report = json.loads(wake_result.split(":", 1)[1])
                report_text  = str(report.get("text") or "")
                report_voice = str(report.get("voice") or "niwat")
                print_status(">> Jarvis Agent: ", report_text)
                speak_text_now(report_text, voice=report_voice)
                continue
            command = recognize_command(device_index)

        if not command:
            continue

        print_status(">> Boss: ", command)
        interrupted_command, payload = stream_and_speak_reply(command, device_index)
        if interrupted_command:
            pending_command = interrupted_command
            continue

        if not isinstance(payload, dict):
            continue

        print_status(">> Jarvis: ", str(payload.get("reply_text") or ""))

        action = payload.get("action", {})
        if not isinstance(action, dict):
            action = {}

        action_type = str(action.get("type") or "").lower()
        if action_type == "shutdown":
            print_status(">> ", "Shutting down Jarvis Next...")
            break
        elif action_type in {"fetch_web", "morning_brief", "check_gmail", "check_calendar"}:
            print_status(">> ", f"Agent Worker: {action_type}")
            start_agent_worker(action)


if __name__ == "__main__":
    main()
