# Voice Assistant Script (Thai-First)

โปรเจกต์นี้เป็นผู้ช่วยเสียงภาษาไทยบน Windows โดยเน้นคำสั่งภาษาไทยเป็นหลัก และแยกชั้นพูดเสียงออกจากตัว orchestration เพื่อให้ปรับน้ำเสียงและเปลี่ยน provider ได้ง่ายขึ้น

## สิ่งที่เปลี่ยนแล้ว

- ย้าย `GEMINI_API_KEY` ออกจากการใช้งานตรงใน `config.json` ไปใช้ environment variable หรือ `.env`
- เพิ่ม session memory แบบสั้น ๆ เพื่อให้ Jarvis จดจำบริบทล่าสุดของบทสนทนาได้
- เพิ่ม `speech metadata` จากฝั่ง LLM เช่น `tone`, `voice`, `rate`, `pitch`
- แยก TTS เป็น provider layer ใน `pro_speak.py`
- เพิ่ม cache warm-up สำหรับข้อความสั้นที่ใช้บ่อย เพื่อลด latency

## ไฟล์หลัก

- `jarvis.ps1`: orchestrator หลักของระบบ
- `brain.py`: เรียก LLM และคืนผลเป็น JSON พร้อม metadata ของเสียง
- `pro_speak.py`: TTS provider layer และ cache
- `speak.ps1`: PowerShell wrapper สำหรับเรียก TTS
- `jarvis_runtime.py`: helper สำหรับ env และ session memory

## การตั้งค่า API Key

ตั้งค่าแบบชั่วคราวใน PowerShell:

```powershell
$env:GEMINI_API_KEY="your-real-api-key"
```

หรือสร้างไฟล์ `.env` จาก `.env.example` แล้วใส่ค่า:

```env
GEMINI_API_KEY=your-real-api-key
```

ถ้าต้องการใช้เสียงพูดของ Google (ภาษาไทยคุณภาพดีกว่า SAPI ในหลายเครื่อง) ให้ตั้งค่าเพิ่ม:

```env
GOOGLE_TTS_API_KEY=your-google-tts-api-key
GOOGLE_TTS_LANGUAGE=th-TH
GOOGLE_TTS_VOICE_NAME=
```

## วิธีใช้งาน

อ่านข้อความเป็นเสียง:

```powershell
.\speak.ps1 -Text "สวัสดีครับบอส" -Tone friendly
```

ใช้เสียง Google:

```powershell
.\speak.ps1 -Provider google -Text "ทดสอบเสียงไทยจาก Google" -Tone calm
```

ระบุโทนเสียงเพิ่ม:

```powershell
.\speak.ps1 -Text "รับทราบครับบอส" -Tone serious -Rate "-8%" -Pitch "-4Hz"
```

วอร์ม cache อย่างเดียว:

```powershell
.\speak.ps1 -Text "ระบบพร้อมใช้งานครับ" -Tone friendly -Precache
```

โหมด Jarvis:

```powershell
.\jarvis.ps1
```

## หมายเหตุ

- ระบบตั้งค่าให้ตอบภาษาไทยเป็นค่าเริ่มต้น
- ถ้า `python` หรือ dependency ยังไม่พร้อม ระบบจะรันไม่ผ่านจนกว่าจะติดตั้ง environment ที่ถูกต้อง
