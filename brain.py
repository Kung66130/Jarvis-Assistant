import io
import json
import re
import sys
from typing import Any

try:
    import google.generativeai as genai
except ImportError:
    genai = None

from jarvis_runtime import get_env_value, load_session_memory, save_session_memory


sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

MODEL_NAME = "gemini-1.5-flash"
MAX_TURNS = 6

DEFAULT_SPEECH = {
    "tone": "friendly",
    "voice": "niwat",
    "rate": "+0%",
    "pitch": "+0Hz",
    "provider": "edge",
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
- ตอบสั้น กระชับ สุภาพ เป็นธรรมชาติ และพร้อมช่วยงานจริง
- วิเคราะห์อารมณ์/สถานการณ์จากคำสั่งภาษาไทย แล้วเลือก tone ที่เหมาะสม
- tone ต้องเป็นหนึ่งใน calm, friendly, cheerful, serious, urgent
- voice ต้องเป็น niwat หรือ premwadee
- rate เป็นรูปแบบเช่น +0%, -10%, +12%
- pitch เป็นรูปแบบเช่น +0Hz, -4Hz, +10Hz
- cache ให้เป็น true เมื่อเป็นข้อความสั้นหรือข้อความที่มีโอกาสถูกใช้ซ้ำ
- ห้ามส่ง markdown, code fence หรือคำอธิบายเพิ่มนอก JSON

บริบทการสนทนาก่อนหน้า:
{history_text}

คำสั่งล่าสุดจากบอส:
{user_text}

ให้ตอบเป็น JSON ตามรูปแบบนี้เท่านั้น:
{{
  "reply_text": "คำตอบภาษาไทย",
  "speech": {{
    "tone": "friendly",
    "voice": "niwat",
    "rate": "+0%",
    "pitch": "+0Hz",
    "provider": "edge",
    "cache": false
  }}
}}
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
    speech["provider"] = "edge"

    tone_hint = TONE_HINTS[tone]
    speech["voice"] = str(speech.get("voice") or tone_hint["voice"]).lower()
    if speech["voice"] not in {"niwat", "premwadee"}:
        speech["voice"] = tone_hint["voice"]

    speech["rate"] = str(speech.get("rate") or tone_hint["rate"])
    speech["pitch"] = str(speech.get("pitch") or tone_hint["pitch"])
    speech["cache"] = bool(speech.get("cache", False))

    # If edge TTS is blocked, allow switching to offline SAPI.
    # The PowerShell layer can override provider; this is just a default hint.
    provider = str(speech.get("provider") or "edge").lower()
    if provider not in {"edge", "sapi"}:
        provider = "edge"
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


def get_ai_response(prompt: str) -> dict[str, Any]:
    turns = load_session_memory(MAX_TURNS)
    model = configure_model()
    full_prompt = build_prompt(prompt, turns)

    response = model.generate_content(
        full_prompt,
        generation_config={"temperature": 0.4},
    )
    payload = extract_json_block(response.text)

    reply_text = str(payload.get("reply_text", "")).strip()
    if not reply_text:
        raise ValueError("Model returned an empty reply_text.")

    speech = normalize_speech(payload.get("speech"))
    turns.append({"user": prompt, "assistant": reply_text, "tone": speech["tone"]})
    save_session_memory(turns)
    return {"reply_text": reply_text, "speech": speech}


if __name__ == "__main__":
    args = sys.argv[1:]
    user_input = " ".join(args).strip()

    if not user_input:
        result = fallback_response("")
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(0)

    try:
        result = get_ai_response(user_input)
    except Exception:
        result = fallback_response(user_input)

    print(json.dumps(result, ensure_ascii=False))
