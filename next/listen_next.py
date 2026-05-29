"""
listen_next.py — Jarvis Next STT Layer
ใช้ faster-whisper (small model) แทน Google Speech API
Wake word detection ยังใช้ openwakeword เหมือนเดิม
"""

from __future__ import annotations

import io
import json
import os
import sys
import wave
import tempfile
from typing import Optional

import numpy as np
import pyaudio

# Parent directory imports (reuse wake detection from original)
_PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PARENT)

# Reuse wake detection and helper functions from original listen.py
from listen import (
    find_input_device,
    wait_for_wake_activity,
    detect_interrupt,
)

# Load config
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config_next.json")
with open(_CONFIG_PATH, encoding="utf-8") as _f:
    _CFG = json.load(_f)

WHISPER_MODEL_SIZE   = _CFG.get("whisper_model", "small")
WHISPER_DEVICE       = _CFG.get("whisper_device", "cpu")
WHISPER_COMPUTE_TYPE = _CFG.get("whisper_compute_type", "int8")

# Audio config
SAMPLE_RATE    = 16000
CHANNELS       = 1
FORMAT         = pyaudio.paInt16
CHUNK_SIZE     = 1024
RECORD_SECONDS = 5       # ระยะเวลาบันทึกสูงสุดต่อคำสั่ง
SILENCE_THRESH = 300     # RMS threshold — หยุดถ้าเงียบ
SILENCE_CHUNKS = 20      # จำนวน chunks เงียบก่อนหยุด (~1.3s)

# Lazy-load Whisper model (โหลดครั้งแรกที่ใช้ ไม่ต้องรอตอน startup)
_whisper_model = None


def _get_whisper() -> "WhisperModel":
    global _whisper_model
    if _whisper_model is None:
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise ImportError(
                "faster-whisper ยังไม่ได้ติดตั้ง — รัน install_next.ps1 ก่อนครับ"
            )
        print(
            f"[Whisper] โหลด model '{WHISPER_MODEL_SIZE}' ({WHISPER_DEVICE}) ...",
            file=sys.stderr,
        )
        _whisper_model = WhisperModel(
            WHISPER_MODEL_SIZE,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE_TYPE,
        )
        print("[Whisper] โหลดสำเร็จ", file=sys.stderr)
    return _whisper_model


# ── Audio Recording ────────────────────────────────────────────────────────

def _rms(data: bytes) -> float:
    """คำนวณ RMS ของ audio chunk (ใช้ตรวจ silence)"""
    if not data:
        return 0.0
    arr = np.frombuffer(data, dtype=np.int16).astype(np.float32)
    return float(np.sqrt(np.mean(arr ** 2))) if len(arr) > 0 else 0.0


def record_until_silence(device_index: Optional[int] = None) -> bytes:
    """
    บันทึก audio จาก mic จนกว่าจะเงียบ หรือครบ RECORD_SECONDS
    คืนค่า raw PCM bytes (16kHz, 16-bit, mono)
    """
    pa = pyaudio.PyAudio()
    stream = pa.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=SAMPLE_RATE,
        input=True,
        input_device_index=device_index,
        frames_per_buffer=CHUNK_SIZE,
    )

    frames: list[bytes] = []
    silent_chunks = 0
    max_chunks = int(SAMPLE_RATE / CHUNK_SIZE * RECORD_SECONDS)

    try:
        for _ in range(max_chunks):
            chunk = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            frames.append(chunk)
            if _rms(chunk) < SILENCE_THRESH:
                silent_chunks += 1
                if silent_chunks >= SILENCE_CHUNKS and len(frames) > SILENCE_CHUNKS:
                    break
            else:
                silent_chunks = 0
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()

    return b"".join(frames)


# ── Transcription ──────────────────────────────────────────────────────────

def transcribe_thai(audio_bytes: bytes) -> str:
    """
    แปลง PCM bytes → text ด้วย faster-whisper
    ลอง lang=th ก่อน ถ้าสั้นเกินไปใช้ auto-detect
    """
    if not audio_bytes:
        return ""

    # แปลง bytes → numpy float32
    audio_np = (
        np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    )

    model = _get_whisper()

    # Thai transcription
    segments, info = model.transcribe(
        audio_np,
        language="th",
        beam_size=5,
        vad_filter=True,           # กรอง silence อัตโนมัติ
        vad_parameters={
            "min_silence_duration_ms": 500,
        },
    )

    text = " ".join(seg.text.strip() for seg in segments).strip()

    # ถ้าผลว่างเปล่า ลอง auto-detect language
    if not text:
        segments2, _ = model.transcribe(audio_np, beam_size=5, vad_filter=True)
        text = " ".join(seg.text.strip() for seg in segments2).strip()

    return text


# ── Public API (same signature as listen.py) ──────────────────────────────

def recognize_command(device_index: Optional[int] = None) -> str:
    """
    บันทึกเสียงและแปลงเป็น text ด้วย Whisper
    API เหมือน listen.recognize_command() เดิมทุกอย่าง
    """
    print("[Whisper] รับฟัง...", file=sys.stderr)
    audio = record_until_silence(device_index)
    if not audio:
        return ""

    text = transcribe_thai(audio)
    print(f"[Whisper] ได้ยิน: {text!r}", file=sys.stderr)
    return text


# re-export สิ่งที่ loop ต้องการ (จาก listen.py เดิม)
__all__ = [
    "find_input_device",
    "wait_for_wake_activity",
    "detect_interrupt",
    "recognize_command",
    "transcribe_thai",
    "record_until_silence",
]
