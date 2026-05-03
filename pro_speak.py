import asyncio
import edge_tts
import os
import sys
import ctypes
import time
import random
import hashlib

VOICES = {
    "niwat":    "th-TH-NiwatNeural",
    "premwadee": "th-TH-PremwadeeNeural",
}
DEFAULT_VOICE = "niwat"

# โฟลเดอร์เก็บคลังเสียง (อยู่ใต้โฟลเดอร์จาวิส)
CACHE_DIR = os.path.join(os.path.dirname(__file__), "voice_cache")
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

def play_mp3(path):
    import subprocess
    # ส่งสัญญาณบอก UI ว่ากำลังพูด
    state_file = os.path.join(os.path.dirname(__file__), "state.txt")
    with open(state_file, "w") as f: f.write("SPEAKING")
    
    path = os.path.abspath(path)
    # สคริปต์ PowerShell ที่รอตามความยาวจริงของไฟล์ (เพิ่ม Timeout 2 วินาทีกันค้าง)
    ps_script = (
        "Add-Type -AssemblyName PresentationCore; "
        "$p = New-Object System.Windows.Media.MediaPlayer; "
        f"$p.Open('{path}'); "
        "$i = 0; while ($p.NaturalDuration.HasTimeSpan -eq $false -and $i -lt 100) { Start-Sleep -m 20; $i++ }; "
        "$p.Play(); "
        "if ($p.NaturalDuration.HasTimeSpan) { Start-Sleep -s ($p.NaturalDuration.TimeSpan.TotalSeconds + 0.5) } else { Start-Sleep -s 5 }"
    )
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script])
    
    # กลับสู่สถานะว่างงาน
    with open(state_file, "w") as f: f.write("IDLE")
    return True

async def speak(text, voice_key=DEFAULT_VOICE, rate="+0%", pitch="+0Hz", only_cache=False):
    voice = VOICES.get(voice_key, VOICES[DEFAULT_VOICE])
    text_hash = hashlib.md5(f"{text}_{voice}_{rate}_{pitch}".encode()).hexdigest()
    cache_path = os.path.join(CACHE_DIR, f"{text_hash}.mp3")

    if os.path.exists(cache_path):
        if not only_cache:
            play_mp3(cache_path)
        return

    for attempt in range(3):
        try:
            communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
            await communicate.save(cache_path)
            if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
                break
        except Exception:
            time.sleep(1)

    if os.path.exists(cache_path) and not only_cache:
        play_mp3(cache_path)

if __name__ == "__main__":
    args = sys.argv[1:]
    # เพิ่ม flag --cache เพื่อโหลดอย่างเดียว
    only_cache = False
    if args and args[0] == "--cache":
        only_cache = True
        args = args[1:]
        
    text = " ".join(args) if args else "สวัสดีครับบอส ผมจาวิสพร้อมรับใช้ครับ"
    asyncio.run(speak(text, only_cache=only_cache))
