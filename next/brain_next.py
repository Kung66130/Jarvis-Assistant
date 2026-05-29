"""
brain_next.py — Jarvis Next Brain
Gemini 2.5 Flash + Native Function Calling (แทน JSON prompt engineering)
ไม่แตะ brain.py เดิมแม้แต่บรรทัดเดียว
"""

from __future__ import annotations

import io
import json
import os
import queue
import sys
import threading
from typing import Any

# Parent directory for shared modules
_PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PARENT)

try:
    import google.generativeai as genai
    from google.generativeai import protos
except ImportError:
    genai = None
    protos = None

from jarvis_runtime import get_env_value, load_session_memory, save_session_memory
from voice_stream import StreamingSegmentBuffer

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# ── Config ─────────────────────────────────────────────────────────────────
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config_next.json")
with open(_CONFIG_PATH, encoding="utf-8") as _f:
    _CFG = json.load(_f)

MODEL_NAME              = _CFG.get("model", "gemini-2.5-flash-preview-05-20")
MAX_TURNS               = 6
MODEL_TIMEOUT_SECONDS   = 25
STREAM_IDLE_TIMEOUT     = 10

SYSTEM_PROMPT = """คุณคือ Jarvis ผู้ช่วย AI ของ "บอส"

กติกา:
- ตอบภาษาไทยเป็นหลัก สั้น กระชับ เป็นธรรมชาติ พร้อมช่วยงานจริง
- ถ้าคำสั่งต้องใช้ข้อมูลภายนอก ให้เรียก tool ที่เหมาะสม
- ถ้าเป็นคำถามทั่วไปที่รู้คำตอบแล้ว ตอบเลยโดยไม่ต้องเรียก tool
- ห้ามตอบยาวเกินความจำเป็น"""

# ── Tool (Function) Declarations ───────────────────────────────────────────
_TOOLS = [
    genai.protos.Tool(function_declarations=[
        genai.protos.FunctionDeclaration(
            name="morning_brief",
            description="ดึงข้อมูลมอนิ่งบรีฟ ประเด็นน่าติดตามจากแหล่งข้อมูลการเงิน",
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "date": genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        description="วันที่ เช่น '20 May 2026', 'yesterday', 'latest'",
                    )
                },
            ),
        ),
        genai.protos.FunctionDeclaration(
            name="fetch_web",
            description="ดึงข้อมูลจาก URL ที่กำหนด",
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "url": genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        description="URL ที่ต้องการดึงข้อมูล",
                    )
                },
                required=["url"],
            ),
        ),
        genai.protos.FunctionDeclaration(
            name="check_gmail",
            description="ตรวจสอบและอ่านอีเมล Gmail ล่าสุด",
            parameters=genai.protos.Schema(type=genai.protos.Type.OBJECT, properties={}),
        ),
        genai.protos.FunctionDeclaration(
            name="check_calendar",
            description="ตรวจสอบตารางงานใน Google Calendar วันนี้หรือสัปดาห์นี้",
            parameters=genai.protos.Schema(type=genai.protos.Type.OBJECT, properties={}),
        ),
        genai.protos.FunctionDeclaration(
            name="shutdown",
            description="ปิดระบบ Jarvis",
            parameters=genai.protos.Schema(type=genai.protos.Type.OBJECT, properties={}),
        ),
    ])
] if genai and protos else []


# ── Model Factory ──────────────────────────────────────────────────────────
def _configure_model(*, streaming: bool = False) -> Any:
    if genai is None:
        raise RuntimeError("google-generativeai not installed")
    api_key = get_env_value("GEMINI_API_KEY", allow_legacy_config=True)
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY")
    genai.configure(api_key=api_key)
    tools = [] if streaming else _TOOLS
    return genai.GenerativeModel(
        MODEL_NAME,
        tools=tools,
        system_instruction=SYSTEM_PROMPT,
    )


# ── History ────────────────────────────────────────────────────────────────
def _history_text(turns: list[dict]) -> str:
    if not turns:
        return "ยังไม่มีประวัติการสนทนา"
    lines = []
    for i, t in enumerate(turns[-MAX_TURNS:], 1):
        lines.append(f"{i}. บอส: {t.get('user','')}\n   Jarvis: {t.get('assistant','')}")
    return "\n".join(lines)


def _build_prompt(user_text: str, turns: list[dict]) -> str:
    return (
        f"บริบทก่อนหน้า:\n{_history_text(turns)}\n\n"
        f"คำสั่งล่าสุด: {user_text}"
    )


# ── Extract action from function call ─────────────────────────────────────
def _extract_action(response) -> dict[str, Any]:
    """แปลง function_call response → action dict แบบเดิมที่ agent_worker เข้าใจ"""
    for part in response.parts:
        fc = getattr(part, "function_call", None)
        if fc and fc.name:
            action: dict[str, Any] = {"type": fc.name}
            if hasattr(fc, "args") and fc.args:
                action.update(dict(fc.args))
            return action
    return {}


def _extract_text(response) -> str:
    """ดึง text จาก response (อาจมีหรือไม่มีก็ได้เมื่อ FC ถูกเรียก)"""
    text = ""
    for part in response.parts:
        if hasattr(part, "text") and part.text:
            text += part.text
    return text.strip()


# ── Default speech metadata ────────────────────────────────────────────────
def _default_speech() -> dict[str, Any]:
    return {
        "tone": "friendly",
        "voice": "niwat",
        "rate": "+4%",
        "pitch": "+4Hz",
        "provider": "auto",
        "cache": False,
    }


# ── Main response function ─────────────────────────────────────────────────
def get_ai_response(user_text: str) -> dict[str, Any]:
    """Gemini 2.5 Flash + Function Calling — คืนค่า format เดิมที่ jarvis_loop เข้าใจ"""
    turns = load_session_memory(MAX_TURNS)
    model = _configure_model()
    prompt = _build_prompt(user_text, turns)

    def _call():
        return model.generate_content(
            prompt,
            generation_config={"temperature": 0.4},
            tool_config={"function_calling_config": {"mode": "AUTO"}},
        )

    response = _run_with_timeout(_call, timeout=MODEL_TIMEOUT_SECONDS)

    # Extract action from function call (if any)
    action = _extract_action(response)

    # Get reply text
    reply_text = _extract_text(response)

    # If model called a function with no text reply, generate brief acknowledgment
    if action and not reply_text:
        ack_map = {
            "morning_brief":   "รับทราบครับ กำลังดึงมอนิ่งบรีฟให้ครับบอส",
            "fetch_web":       "รับทราบครับ กำลังดึงข้อมูลจากเว็บให้ครับ",
            "check_gmail":     "รับทราบครับ กำลังเช็คอีเมลให้ครับบอส",
            "check_calendar":  "รับทราบครับ กำลังเช็คตารางงานให้ครับ",
            "shutdown":        "รับทราบครับบอส กำลังปิดระบบจาร์วิสครับ แล้วพบกันใหม่ครับ",
        }
        reply_text = ack_map.get(action["type"], "รับทราบครับ กำลังดำเนินการให้ครับบอส")

    if not reply_text:
        reply_text = "รับทราบครับบอส"

    turns.append({"user": user_text, "assistant": reply_text, "tone": "friendly"})
    save_session_memory(turns)

    return {
        "reply_text": reply_text,
        "speech": _default_speech(),
        "action": action,
    }


# ── Streaming (for low-latency first word) ────────────────────────────────
def stream_ai_reply_text(user_text: str):
    """Streaming text — สำหรับพูดออกเสียงทันทีก่อน full response จะเสร็จ"""
    turns = load_session_memory(MAX_TURNS)
    model = _configure_model(streaming=True)  # ไม่ใช้ FC ใน streaming
    prompt = (
        f"บริบท:\n{_history_text(turns)}\n\n"
        f"คำสั่ง: {user_text}\n\n"
        "ตอบภาษาไทย สั้น กระชับ ธรรมชาติ ห้าม markdown"
    )

    buffer = StreamingSegmentBuffer(max_chars=70)
    event_q: queue.Queue[tuple[str, Any]] = queue.Queue()

    def _worker():
        try:
            resp = model.generate_content(
                prompt,
                generation_config={"temperature": 0.4},
                stream=True,
            )
            for chunk in resp:
                txt = getattr(chunk, "text", "") or ""
                if txt:
                    event_q.put(("chunk", txt))
            event_q.put(("done", None))
        except Exception as exc:
            event_q.put(("error", exc))

    threading.Thread(target=_worker, daemon=True).start()

    while True:
        try:
            kind, payload = event_q.get(timeout=STREAM_IDLE_TIMEOUT)
        except queue.Empty as exc:
            raise TimeoutError("Stream timeout") from exc

        if kind == "chunk":
            for seg in buffer.push(str(payload or "")):
                yield seg
        elif kind == "error":
            raise payload
        elif kind == "done":
            remainder = buffer.flush()
            if remainder:
                yield remainder
            return


# ── Timeout helper ─────────────────────────────────────────────────────────
def _run_with_timeout(fn, *, timeout: float):
    q: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)

    def _worker():
        try:
            q.put((True, fn()))
        except Exception as exc:
            q.put((False, exc))

    threading.Thread(target=_worker, daemon=True).start()
    try:
        ok, val = q.get(timeout=timeout)
    except queue.Empty as exc:
        raise TimeoutError(f"Timeout after {timeout}s") from exc

    if ok:
        return val
    raise val


# ── Fallback ───────────────────────────────────────────────────────────────
def fallback_response(user_text: str) -> dict[str, Any]:
    return {
        "reply_text": "ขออภัยครับบอส สมองมีปัญหาชั่วคราว กรุณาลองใหม่ครับ",
        "speech": _default_speech(),
        "action": {},
    }
