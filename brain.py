import io
import json
import re
import subprocess
import sys
import argparse
import queue
import threading
import time
from typing import Any
import requests

try:
    import google.generativeai as genai
except ImportError:
    genai = None

from jarvis_runtime import get_default_tts_provider, get_env_value, load_session_memory, save_session_memory
from voice_stream import StreamingSegmentBuffer


sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

MODEL_NAME = "gemini-2.5-flash"
MAX_TURNS = 6
MODEL_TIMEOUT_SECONDS = 20
STREAM_IDLE_TIMEOUT_SECONDS = 30
OLLAMA_STARTUP_TIMEOUT_SECONDS = 12  # Max seconds to wait for ollama to start

# ---------------------------------------------------------------------------
# Ollama lifecycle helpers — start on demand, stop when done
# ---------------------------------------------------------------------------

def _is_ollama_running() -> bool:
    """Return True if the Ollama API is responsive at localhost:11434."""
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def _start_ollama() -> bool:
    """Start ollama serve in background (no console window) and wait until ready."""
    if _is_ollama_running():
        return True  # Already up, nothing to do

    try:
        CREATE_NO_WINDOW = 0x08000000  # Windows flag: no visible console
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
        )
    except Exception as e:
        print(f"DEBUG: Could not launch ollama: {e}", file=sys.stderr)
        return False

    # Poll until Ollama is ready or timeout
    deadline = time.time() + OLLAMA_STARTUP_TIMEOUT_SECONDS
    while time.time() < deadline:
        time.sleep(1)
        if _is_ollama_running():
            print("DEBUG: Ollama started successfully.", file=sys.stderr)
            return True

    print("DEBUG: Ollama did not respond within timeout.", file=sys.stderr)
    return False


def _stop_ollama() -> None:
    """Kill the ollama.exe process to free RAM/GPU after use."""
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "ollama.exe"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        print("DEBUG: Ollama stopped.", file=sys.stderr)
    except Exception as e:
        print(f"DEBUG: Could not stop ollama: {e}", file=sys.stderr)

DEFAULT_SPEECH = {
    "tone": "friendly",
    "voice": "niwat",
    "rate": "+0%",
    "pitch": "+0Hz",
    "provider": "auto",
    "cache": False,
}

TONE_HINTS = {
    "calm": {"rate": "-12%", "pitch": "-4Hz", "voice": "niwat"},
    "friendly": {"rate": "+4%", "pitch": "+4Hz", "voice": "niwat"},
    "cheerful": {"rate": "+12%", "pitch": "+12Hz", "voice": "premwadee"},
    "serious": {"rate": "-8%", "pitch": "-6Hz", "voice": "niwat"},
    "urgent": {"rate": "+10%", "pitch": "+6Hz", "voice": "niwat"},
}


def configure_model():
    if genai is None:
        raise RuntimeError(
            "Missing dependency: google.generativeai. Install project dependencies before running Jarvis."
        )

    api_key = get_env_value("GEMINI_API_KEY", allow_legacy_config=True)
    if not api_key:
        raise RuntimeError(
            "Missing GEMINI_API_KEY. Set it in the environment or .env before running Jarvis."
        )

    genai.configure(api_key=api_key)
    return genai.GenerativeModel(MODEL_NAME)


def build_history_text(turns: list[dict[str, Any]]) -> str:
    if not turns:
        return "ยังไม่มีประวัติการสนทนาก่อนหน้า"

    lines = []
    for index, turn in enumerate(turns[-MAX_TURNS:], start=1):
        user_text = turn.get("user", "")
        assistant_text = turn.get("assistant", "")
        tone = turn.get("tone", "friendly")
        lines.append(
            f"{index}. ผู้ใช้: {user_text}\n   Jarvis: {assistant_text}\n   น้ำเสียงล่าสุด: {tone}"
        )
    return "\n".join(lines)


def build_prompt(user_text: str, turns: list[dict[str, Any]]) -> str:
    history_text = build_history_text(turns)
    return f"""
คุณคือ Jarvis ผู้ช่วย AI ของ "บอส"

กติกา:
- ผู้ใช้สั่งงานเป็นภาษาไทยเป็นหลัก ให้ตอบไทยเป็นค่าเริ่มต้น เว้นแต่ผู้ใช้ขอภาษาอื่น
- ตอบสุภาพ เป็นธรรมชาติ และพร้อมช่วยงานจริง โดยเขียนคำตอบด้วยรูปแบบที่สวยงามเป็นระบบ (ใช้ *ตัวหนา* สำหรับหัวข้อหรือข้อความสำคัญ, ทำเป็นรายการหัวข้อย่อยด้วยเครื่องหมาย •, เว้นวรรคจัดย่อหน้าให้อ่านง่าย และใส่ Emojis ที่เหมาะสม เพื่อให้ข้อความออกมาสวยงามระดับพรีเมียมเหมือนหน้าแชตบอทชั้นนำ)
- วิเคราะห์อารมณ์/สถานการณ์จากคำสั่งภาษาไทย แล้วเลือก tone ที่เหมาะสม
- tone ต้องเป็นหนึ่งใน calm, friendly, cheerful, serious, urgent
- voice ต้องเป็น niwat หรือ premwadee
- rate เป็นรูปแบบเช่น +0%, -10%, +12%
- pitch เป็นรูปแบบเช่น +0Hz, -4Hz, +10Hz
- cache ให้เป็น true เมื่อเป็นข้อความสั้นหรือข้อความที่มีโอกาสถูกใช้ซ้ำ
- หากผู้ใช้สั่งงานที่ต้องใช้ Agent เช่น ค้นหาข้อมูลจากเว็บไซต์, ดึงข้อมูลจาก URL ให้ใส่ action เป็น fetch_web พร้อม url
- หากผู้ใช้สั่งให้ดึงข้อมูลข่าวมอนิ่งบรีฟ หรือ morning brief ให้ใส่ action type เป็น morning_brief และถ้าผู้ใช้ระบุวันที่ (เช่น เมื่อวาน, 19 May) ให้ระบุ date ใน action ด้วย (เช่น "19 May", "yesterday", "latest")
- หากผู้ใช้สั่งงานเกี่ยวกับ Gmail หรือ ปฏิทิน Google Calendar เช่น เช็คเมลล่าสุด หรือ เช็คตารางงาน ให้ระบุ action type เป็น check_gmail หรือ check_calendar ตามลำดับ
- หากผู้ใช้สั่งให้ "เปิดระบบสั่งจากมือถือ" หรือ "เปิดระบบรีโมท" ให้ระบุ action type เป็น start_remote_approver
- หากผู้ใช้สั่งงานให้เขียนโค้ด, สร้างสคริปต์, จัดการไฟล์, รันคำสั่ง Terminal, ค้นหาข้อมูลล่าสุดบนอินเทอร์เน็ต ข่าวสารในวันนี้ ข้อมูลราคาหุ้น/น้ำมัน/ทองคำ หรือการวิเคราะห์สืบค้นที่ซับซ้อน ให้ระบุ action type เป็น run_agentic_task พร้อมฟิลด์ prompt อธิบายงานสืบค้นอย่างละเอียด (เช่น "ค้นหาและสรุปราคาน้ำมันวันนี้ให้บอสฟัง")
- หากผู้ใช้สั่งให้ปิดระบบ, ปิดเครื่อง, หรือหยุดทำงาน ให้ใส่ action เป็น shutdown
- ห้ามครอบกล่อง JSON ด้วย Markdown code fence (```json) หรือพิมพ์คำอธิบายอื่นใดนอกเนื้อหา JSON โดยเด็ดขาด
- ตัวแปร "reply_text" ภายใน JSON สามารถเขียนเป็นรูปแบบ Markdown (เช่น *ตัวหนา*, รายการข้อความ, เว้นบรรทัด) เพื่อแสดงผลบน Telegram ได้อย่างสวยงาม
- หมายเหตุสำหรับระบบออกเสียง (TTS): เครื่องหมาย Markdown เช่น * ใน reply_text จะถูกกรองออกอัตโนมัติสำหรับการอ่านออกเสียง ดังนั้นในส่วนแชตสามารถจัดรูปแบบเต็มที่ได้เลย

บริบทการสนทนาก่อนหน้า:
{history_text}

คำสั่งล่าสุดจากบอส:
{user_text}

ให้ตอบเป็น JSON ตามรูปแบบนี้เท่านั้น:
{{
  "reply_text": "คำตอบภาษาไทย (เช่น รับทราบครับบอส กำลังดึงข้อมูลมอนิ่งบรีฟให้ครับ)",
  "speech": {{
    "tone": "friendly",
    "voice": "niwat",
    "rate": "+0%",
    "pitch": "+0Hz",
    "provider": "auto",
    "cache": false
  }},
  "action": {{
    "type": "fetch_web หรือ morning_brief หรือ check_gmail หรือ check_calendar หรือ start_remote_approver หรือ run_agentic_task หรือ shutdown",
    "url": "URL ที่ต้องการ (สำหรับ fetch_web เท่านั้น)",
    "date": "วันที่ต้องการดึง (สำหรับ morning_brief เท่านั้น เช่น 20 May 2026 หรือ yesterday)",
    "prompt": "คำสั่งหรือเป้าหมายที่ต้องการให้ Agent ทำอย่างละเอียด (สำหรับ run_agentic_task เท่านั้น)"
  }}
}}
*หมายเหตุ: action ให้ใส่ {{}} หากไม่มีงานที่ต้องใช้ Agent*
""".strip()


def build_stream_prompt(user_text: str, turns: list[dict[str, Any]]) -> str:
    history_text = build_history_text(turns)
    return f"""
คุณคือ Jarvis ผู้ช่วย AI ของ "บอส"

กติกา:
- ตอบเป็นภาษาไทยสั้น กระชับ ธรรมชาติ และพร้อมพูดออกเสียงได้ทันที
- ห้ามตอบเป็น JSON
- ห้ามใส่ markdown, bullet, code fence, หรือคำอธิบายประกอบ
- ถ้าคำสั่งเป็นแนวให้ไปค้นข้อมูลหรือทำงานต่อ ให้ตอบเป็นคำยืนยันสั้น ๆ ก่อน เช่น "กำลังตรวจสอบให้ครับบอส"
- ถ้าคำสั่งเป็นคำถามทั่วไป ให้ตอบเป็นคำตอบจริงได้เลย แต่ไม่ยาวเกินจำเป็น

บริบทการสนทนาก่อนหน้า:
{history_text}

คำสั่งล่าสุดจากบอส:
{user_text}
""".strip()


def extract_json_block(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def normalize_speech(raw_speech: dict[str, Any] | None) -> dict[str, Any]:
    speech = DEFAULT_SPEECH.copy()
    if isinstance(raw_speech, dict):
        speech.update({k: v for k, v in raw_speech.items() if v not in (None, "")})

    tone = str(speech.get("tone", "friendly")).lower()
    if tone not in TONE_HINTS:
        tone = "friendly"

    speech["tone"] = tone
    speech["provider"] = get_default_tts_provider()

    tone_hint = TONE_HINTS[tone]
    speech["voice"] = str(speech.get("voice") or tone_hint["voice"]).lower()
    if speech["voice"] not in {"niwat", "premwadee"}:
        speech["voice"] = tone_hint["voice"]

    speech["rate"] = str(speech.get("rate") or tone_hint["rate"])
    speech["pitch"] = str(speech.get("pitch") or tone_hint["pitch"])
    speech["cache"] = bool(speech.get("cache", False))

    # If edge TTS is blocked, allow switching to offline SAPI.
    # The PowerShell layer can override provider; this is just a default hint.
    provider = str(speech.get("provider") or get_default_tts_provider()).lower()
    if provider not in {"edge", "sapi", "auto"}:
        provider = get_default_tts_provider()
    speech["provider"] = provider
    return speech


def fallback_response(user_text: str) -> dict[str, Any]:
    text = (
        "รับทราบครับบอส ผมจะตอบเป็นภาษาไทยและจัดน้ำเสียงให้นุ่มขึ้นจากระบบเดิม "
        "แต่ตอนนี้สมองส่วนวิเคราะห์มีปัญหาชั่วคราว"
    )
    cache = len(user_text) < 40
    speech = normalize_speech({"tone": "calm", "cache": cache})
    return {"reply_text": text, "speech": speech}


def run_with_timeout(fn, *, timeout_seconds: float):
    result_queue: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)

    def worker():
        try:
            result_queue.put((True, fn()))
        except Exception as exc:
            result_queue.put((False, exc))

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    try:
        ok, value = result_queue.get(timeout=timeout_seconds)
    except queue.Empty as exc:
        raise TimeoutError(f"Operation timed out after {timeout_seconds} seconds.") from exc

    if ok:
        return value
    raise value


def get_ollama_fallback_response(prompt: str, turns: list[dict[str, Any]]) -> dict[str, Any]:
    # Auto-start Ollama on demand
    if not _start_ollama():
        print("DEBUG: Ollama unavailable, using hardcoded fallback.", file=sys.stderr)
        return fallback_response(prompt)

    url = "http://localhost:11434/api/generate"
    full_prompt = build_prompt(prompt, turns)

    model_name = "llama3"
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        if r.status_code == 200:
            models_list = r.json().get("models", [])
            if models_list:
                model_name = models_list[0].get("name")
    except Exception:
        pass

    print(f"DEBUG: Using Ollama model: {model_name}", file=sys.stderr)
    body = {
        "model": model_name,
        "prompt": full_prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.4},
    }

    try:
        r = requests.post(url, json=body, timeout=60)
        if r.status_code == 200:
            res_text = r.json().get("response", "")
            result = extract_json_block(res_text)
            return result
        else:
            raise RuntimeError(f"Ollama returned status code {r.status_code}")
    except Exception as e:
        print(f"DEBUG: Ollama fallback failed: {e}", file=sys.stderr)
        return fallback_response(prompt)
    finally:
        # Stop Ollama to free resources after use
        _stop_ollama()

def get_ai_response(prompt: str) -> dict[str, Any]:
    turns = load_session_memory(MAX_TURNS)
    
    try:
        model = configure_model()
        full_prompt = build_prompt(prompt, turns)

        response = run_with_timeout(
            lambda: model.generate_content(
                full_prompt,
                generation_config={"temperature": 0.4},
            ),
            timeout_seconds=MODEL_TIMEOUT_SECONDS,
        )
        payload = extract_json_block(response.text)
    except Exception as gemini_err:
        print(f"DEBUG: Gemini failed, falling back to Ollama. Error: {gemini_err}", file=sys.stderr)
        payload = get_ollama_fallback_response(prompt, turns)

    reply_text = str(payload.get("reply_text", "")).strip()
    if not reply_text:
        reply_text = "ขออภัยครับบอส สมองขัดข้องชั่วคราว"

    speech = normalize_speech(payload.get("speech"))
    action = payload.get("action", {})
    
    turns.append({"user": prompt, "assistant": reply_text, "tone": speech["tone"]})
    save_session_memory(turns)
    
    return {"reply_text": reply_text, "speech": speech, "action": action}

def stream_ollama_fallback_text(prompt: str, turns: list[dict[str, Any]]):
    # Auto-start Ollama on demand
    if not _start_ollama():
        print("DEBUG: Ollama unavailable for streaming, using hardcoded fallback.", file=sys.stderr)
        fallback_text = fallback_response(prompt)["reply_text"]
        segment_buffer = StreamingSegmentBuffer(max_chars=70)
        for segment in segment_buffer.push(fallback_text):
            yield segment
        remainder = segment_buffer.flush()
        if remainder:
            yield remainder
        return

    stream_prompt = build_stream_prompt(prompt, turns)
    segment_buffer = StreamingSegmentBuffer(max_chars=70)

    model_name = "llama3"
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        if r.status_code == 200:
            models_list = r.json().get("models", [])
            if models_list:
                model_name = models_list[0].get("name")
    except Exception:
        pass

    url = "http://localhost:11434/api/generate"
    body = {
        "model": model_name,
        "prompt": stream_prompt,
        "stream": True,
        "options": {"temperature": 0.4},
    }

    try:
        r = requests.post(url, json=body, stream=True, timeout=60)
        if r.status_code == 200:
            for line in r.iter_lines():
                if line:
                    chunk = json.loads(line.decode("utf-8"))
                    chunk_text = chunk.get("response", "")
                    if chunk_text:
                        for segment in segment_buffer.push(chunk_text):
                            yield segment
            remainder = segment_buffer.flush()
            if remainder:
                yield remainder
        else:
            raise RuntimeError(f"Ollama returned status code {r.status_code}")
    except Exception as e:
        print(f"DEBUG: Ollama stream fallback failed: {e}", file=sys.stderr)
        fallback_text = fallback_response(prompt)["reply_text"]
        for segment in segment_buffer.push(fallback_text):
            yield segment
        remainder = segment_buffer.flush()
        if remainder:
            yield remainder
    finally:
        # Stop Ollama to free resources after streaming completes
        _stop_ollama()

def stream_ai_reply_text(prompt: str):
    turns = load_session_memory(MAX_TURNS)
    
    try:
        model = configure_model()
        stream_prompt = build_stream_prompt(prompt, turns)
        segment_buffer = StreamingSegmentBuffer(max_chars=70)
        event_queue: queue.Queue[tuple[str, str | Exception | None]] = queue.Queue()

        def worker() -> None:
            try:
                response = model.generate_content(
                    stream_prompt,
                    generation_config={"temperature": 0.4},
                    stream=True,
                )
                for chunk in response:
                    chunk_text = getattr(chunk, "text", "") or ""
                    if chunk_text:
                        event_queue.put(("chunk", chunk_text))
                event_queue.put(("done", None))
            except Exception as exc:
                event_queue.put(("error", exc))

        threading.Thread(target=worker, daemon=True).start()

        while True:
            try:
                kind, payload = event_queue.get(timeout=STREAM_IDLE_TIMEOUT_SECONDS)
            except queue.Empty as exc:
                raise TimeoutError(
                    f"Streaming response timed out after {STREAM_IDLE_TIMEOUT_SECONDS} seconds of inactivity."
                ) from exc

            if kind == "chunk":
                for segment in segment_buffer.push(str(payload or "")):
                    yield segment
                continue
            if kind == "error":
                raise payload
            if kind == "done":
                remainder = segment_buffer.flush()
                if remainder:
                    yield remainder
                return
    except Exception as gemini_err:
        print(f"DEBUG: Gemini streaming failed, falling back to Ollama streaming. Error: {gemini_err}", file=sys.stderr)
        yield from stream_ollama_fallback_text(prompt, turns)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", default="")
    parser.add_argument("--stream-reply", action="store_true")
    parser.add_argument("text_parts", nargs="*")
    parsed = parser.parse_args()

    user_input = (parsed.text or " ".join(parsed.text_parts)).strip()

    if not user_input:
        result = fallback_response("")
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(0)

    if parsed.stream_reply:
        try:
            for segment in stream_ai_reply_text(user_input):
                print(f"STREAM_SEGMENT:{segment}", flush=True)
        except Exception as e:
            print(f"DEBUG: Brain stream error: {e}", file=sys.stderr)
            fallback_buffer = StreamingSegmentBuffer(max_chars=70)
            for segment in fallback_buffer.push(fallback_response(user_input)["reply_text"]):
                print(f"STREAM_SEGMENT:{segment}", flush=True)
            remainder = fallback_buffer.flush()
            if remainder:
                print(f"STREAM_SEGMENT:{remainder}", flush=True)
        sys.exit(0)

    try:
        result = get_ai_response(user_input)
    except Exception as e:
        # For debugging, we can print to stderr
        print(f"DEBUG: Brain error: {e}", file=sys.stderr)
        result = fallback_response(user_input)

    # PowerShell looks for this prefix
    print(f"RESPONSE:{json.dumps(result, ensure_ascii=False)}")
