from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

from brain import fallback_response, get_ai_response, stream_ai_reply_text
from listen import detect_interrupt, find_input_device, recognize_command, wait_for_wake_activity
from speech_controller import SegmentSpeaker
from voice_stream import split_for_speech


APP_DIR = Path(__file__).resolve().parent


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
        return

    subprocess.Popen(
        [sys.executable, str(worker_path), json.dumps(action, ensure_ascii=False)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def speak_text_now(text: str, voice: str = "niwat") -> None:
    speaker = SegmentSpeaker(voice=voice)
    clean_text = re.sub(r'[\*_#`~]', '', text)
    speaker.extend(split_for_speech(clean_text, max_chars=70))
    speaker.finish()
    speaker.join()


def stream_and_speak_reply(command: str, device_index: int | None):
    speaker = SegmentSpeaker()
    stream_done = threading.Event()
    full_done = threading.Event()
    speaker_finalized = False
    payload_box: dict[str, object] = {}
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
                    clean_reply = re.sub(r'[\*_#`~]', '', str(payload.get("reply_text") or ""))
                    speaker.extend(split_for_speech(clean_reply, max_chars=70))
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


def send_to_telegram(reply_text: str, photo_path: str | None = None, chat_id: int | None = None) -> None:
    import re
    # Strip <thinking>...</thinking> or 💭 [Thinking]: ... patterns
    reply_text = re.sub(r'<thinking>.*?</thinking>', '', reply_text, flags=re.DOTALL)
    reply_text = re.sub(r'💭 \[\s*Thinking\s*\]:.*?(?=\n\n|\Z)', '', reply_text, flags=re.DOTALL).strip()
    
    resp_file = APP_DIR / "telegram_resp.json"
    try:
        data = {
            "reply_text": reply_text,
            "photo_path": photo_path,
            "chat_id": chat_id,
            "timestamp": time.time()
        }
        with open(resp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        print_status(">> Failed to write Telegram response: ", str(e))


def handle_agent_report(wake_result: str) -> None:
    try:
        report = json.loads(wake_result.split(":", 1)[1])
        report_text = str(report.get("text") or "")
        report_voice = str(report.get("voice") or "niwat")
        photo_path = report.get("photo_path")
        chat_id = report.get("chat_id")
        print_status(">> Jarvis Agent: ", report_text)
        
        # Speak locally only if NOT triggered from Telegram
        if report.get("source") != "telegram":
            speak_text_now(report_text, voice=report_voice)
        
        # Send report back to Telegram chat
        send_to_telegram(f"📢 *[Agent Report]*\n\n{report_text}", photo_path=photo_path, chat_id=chat_id)
    except Exception as e:
        print_status(">> Error processing agent report: ", str(e))


def handle_telegram_cmd(wake_result: str) -> bool:
    try:
        tg_data = json.loads(wake_result.split(":", 1)[1])
        command = tg_data.get("command")
        chat_id = tg_data.get("chat_id")
        print_status(">> Telegram User: ", command)
        
        # For Telegram commands, get direct AI response without local speech or streaming
        try:
            payload = get_ai_response(command)
        except Exception as exc:
            print_status(">> Brain error for Telegram: ", str(exc))
            payload = fallback_response(command)
        
        if isinstance(payload, dict):
            reply_text = str(payload.get("reply_text") or "")
            # Send the immediate answer back to Telegram
            send_to_telegram(reply_text, chat_id=chat_id)
            
            action = payload.get("action", {})
            if isinstance(action, dict) and action.get("type"):
                action_type = str(action.get("type") or "").lower()
                if action_type == "shutdown":
                    print_status(">> ", "Shutting down Jarvis system...")
                    return False
                elif action_type in ["fetch_web", "morning_brief", "check_gmail", "check_calendar", "start_remote_approver", "run_agentic_task"]:
                    print_status(">> ", f"Starting Agent Worker for {action_type}...")
                    action["source"] = "telegram"
                    action["chat_id"] = chat_id
                    start_agent_worker(action)
    except Exception as ex:
        print_status(">> Telegram command error: ", str(ex))
    return True


def handle_voice_interaction(command: str, device_index: int | None) -> tuple[str | None, bool]:
    print_status(">> Boss: ", command)
    interrupted_command, payload = stream_and_speak_reply(command, device_index)
    if interrupted_command:
        return interrupted_command, True

    if not isinstance(payload, dict):
        return None, True

    print_status(">> Jarvis: ", str(payload.get("reply_text") or ""))
    action = payload.get("action", {})
    if not isinstance(action, dict):
        action = {}

    action_type = str(action.get("type") or "").lower()
    if action_type == "shutdown":
        print_status(">> ", "Shutting down Jarvis system...")
        return None, False
    elif action_type in ["fetch_web", "morning_brief", "check_gmail", "check_calendar", "start_remote_approver", "run_agentic_task"]:
        print_status(">> ", f"Starting Agent Worker for {action_type}...")
        start_agent_worker(action)
    return None, True


def main() -> None:
    device_index = find_input_device()
    if device_index is None:
        print_status(">> ", "EDIFIER mic not found, using default.")

    print_status(">> ", "--- Jarvis Agentic System (Streaming Edition) ---")
    speak_text_now("ระบบจาร์วิสออนไลน์ พร้อมรับคำสั่งครับบอส")

    pending_command: str | None = None
    while True:
        if pending_command:
            command = pending_command
            pending_command = None
        else:
            wake_result = wait_for_wake_activity(device_index)
            
            # 1. Handle Agent reports
            if wake_result and wake_result.startswith("AGENT_REPORT:"):
                handle_agent_report(wake_result)
                continue

            # 2. Handle Telegram chat commands
            elif wake_result and wake_result.startswith("TELEGRAM_CMD:"):
                keep_running = handle_telegram_cmd(wake_result)
                if not keep_running:
                    break
                continue

            command = recognize_command(device_index)

        if not command:
            continue

        pending_command, keep_running = handle_voice_interaction(command, device_index)
        if not keep_running:
            break


if __name__ == "__main__":
    main()
