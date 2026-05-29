# 🔐 PERMISSIONS — Jarvis Assistant

เอกสารนี้ระบุสิทธิ์ (Permissions) ทั้งหมดที่ระบบ Jarvis Assistant ต้องการ เพื่อให้ AI ทำงานได้อย่างลื่นไหลโดยไม่ต้องกดอนุมัติซ้ำซ้อนในระหว่างการทำงาน  
ให้บอสอนุมัติสิทธิ์เหล่านี้ **ครั้งเดียวตอนเริ่มต้น Session** ก็เพียงพอครับ

---

## ⚡ Maximum Permission Grant (อนุญาตสูงสุด — คัดลอกไปใช้ได้เลย)

เมื่อเปิด Conversation ใหม่หรือต้องการให้ระบบทำงานเต็มรูปแบบ ให้พิมพ์คำสั่งด้านล่างนี้เพื่อ Grant สิทธิ์ทั้งหมดในคราวเดียวครับ:

```
Please grant the following permissions for this session:
- write_file: C:\Project\Jarvis Assistant
- command: C:\Users\kung6\AppData\Local\Programs\Python\Python312\python.exe
- command: powershell.exe
- command: git
- command: dir
- command: &
- read_url: sbito.co.th
- read_file: C:\Project\AI-Superpowers-Hub
- read_file: C:\Project\GLOBAL_AI_RULES.md
```

---

## 📋 รายละเอียดสิทธิ์ทั้งหมดที่ใช้งาน

### 1. 📂 File System Permissions

| ขอบเขต | Action | เหตุผล |
|--------|--------|---------|
| `C:\Project\Jarvis Assistant` | `read + write` | Workspace หลักของโปรเจค — AI ต้องอ่าน/เขียนไฟล์ทุกไฟล์ในนี้ |
| `C:\Project\AI-Superpowers-Hub` | `read` | อ่านไฟล์ Skill & Global Instructions ที่ใช้ร่วมกัน |
| `C:\Project\GLOBAL_AI_RULES.md` | `read` | กฎส่วนกลางที่ใช้กับทุกโปรเจค |

> [!IMPORTANT]
> **ไฟล์ `.env`** มีสิทธิ์เป็น `ask` โดย default — AI จะขออนุมัติก่อนอ่านทุกครั้ง เพราะมี API Key อยู่ภายใน ถือว่าเป็นพฤติกรรมที่ถูกต้องและปลอดภัยครับ

---

### 2. 🐍 Python Runtime Permissions

| คำสั่ง | เหตุผล |
|--------|---------|
| `C:\Users\kung6\AppData\Local\Programs\Python\Python312\python.exe` | รัน Script หลักทุกตัว: `jarvis_loop.py`, `brain.py`, `agent_worker.py`, `ui_qt.py` |

> [!TIP]
> Grant ครั้งเดียวต่อ Session — ใช้ได้ทุกครั้งที่ AI ต้องการรัน Python

---

### 3. 🖥️ Shell / System Command Permissions

| คำสั่ง | เหตุผล |
|--------|---------|
| `powershell.exe` | รัน `jarvis.ps1`, `speak.ps1`, `bootstrap.ps1` |
| `git` | ดู status, commit, push โปรเจค |
| `dir` / `Get-ChildItem` | สำรวจโครงสร้างไฟล์ |
| `&` (Call operator) | เรียก Python หรือ Script โดยตรงจาก PowerShell |
| `echo` / `date` | คำสั่งยูทิลิตี้ทั่วไป |

---

### 4. 🌐 Network / URL Permissions

| Domain | เหตุผล |
|--------|---------|
| `sbito.co.th` | ดึงบทวิเคราะห์หลักทรัพย์ Morning Brief รายวัน (PDF) |

> [!NOTE]
> URL อื่นนอกเหนือจากนี้จะยัง `ask` ทุกครั้ง เพื่อความปลอดภัยของระบบครับ

---

## 🔒 สิทธิ์ที่ควรเก็บเป็น `ask` (ไม่ควร Grant ถาวร)

| ขอบเขต | เหตุผล |
|--------|---------|
| `.env`, `.env.local` | มี API Key และ Credentials ห้าม AI อ่านโดยไม่ขออนุมัติ |
| `command: *` (Wildcard) | อันตรายเกินไป — อาจรันคำสั่งที่ไม่ต้องการ |
| `read_url: *` (Wildcard) | เปิดกว้างเกินไป — ควรระบุ Domain เฉพาะที่ใช้ |

---

## 🚀 Quick Start — สิทธิ์ขั้นต่ำในการรันระบบ Jarvis

ถ้าต้องการ Grant สิทธิ์น้อยที่สุดเพื่อเปิดใช้งานระบบ Jarvis แบบพื้นฐาน:

```
Grant write_file for: C:\Project\Jarvis Assistant
Grant command for: C:\Users\kung6\AppData\Local\Programs\Python\Python312\python.exe
Grant command for: powershell.exe
```

---

## 📝 บันทึกสิทธิ์ที่อนุมัติไปแล้ว (Granted Permissions Log)

| วันที่ | สิทธิ์ | หมายเหตุ |
|--------|--------|----------|
| 2026-05-20 | `python.exe` (หลายครั้ง) | รัน agent_worker, ui_qt, jarvis_loop |
| 2026-05-20 | `read_url: sbito.co.th` | ดึง Morning Brief PDF |
| 2026-05-20 | `read_file: C:\Project\AI-Superpowers-Hub` | อ่าน Global Instructions |
| 2026-05-20 | `git status`, `dir` | สำรวจโครงสร้างโปรเจค |
| 2026-05-20 | `& (Call operator)` | รัน ui_qt.py, jarvis.ps1 เบื้องหลัง |

---

## 💡 คำแนะนำการใช้งานร่วมกับ AI

1. **เปิด Session ใหม่**: ให้ Copy คำสั่ง Grant จากส่วน "Maximum Permission Grant" ด้านบนไปพิมพ์ก่อนเสมอ
2. **งานที่ทำซ้ำบ่อย** (เช่น รัน Jarvis, ดึง Morning Brief): Grant `python.exe` + `powershell.exe` ก็เพียงพอ
3. **งานพัฒนาโค้ด** (แก้ไฟล์, debug): ต้องการ `write_file: C:\Project\Jarvis Assistant` เพิ่มด้วย
4. **งานที่เกี่ยวกับ SBITO**: ต้องการ `read_url: sbito.co.th` เพิ่มด้วย
