# install_next.ps1
# ติดตั้ง dependencies สำหรับ Jarvis Next Stack
# รัน: .\next\install_next.ps1

$Python = "C:\Users\kung6\AppData\Local\Programs\Python\Python312\python.exe"

Write-Host "=== Jarvis Next — ติดตั้ง Dependencies ===" -ForegroundColor Cyan

Write-Host "`n[1/3] faster-whisper (Whisper STT offline)..." -ForegroundColor Yellow
& $Python -m pip install faster-whisper

Write-Host "`n[2/3] google-genai (Gemini Live API)..." -ForegroundColor Yellow
& $Python -m pip install google-genai

Write-Host "`n[3/3] ตรวจสอบ numpy, pyaudio (ควรมีแล้ว)..." -ForegroundColor Yellow
& $Python -m pip install numpy pyaudio --quiet

Write-Host "`n=== ติดตั้งเสร็จแล้วครับ ===" -ForegroundColor Green
Write-Host 'รัน Jarvis Next:  .\next\jarvis_next.ps1' -ForegroundColor Green
Write-Host 'รัน Live Mode:    .\next\jarvis_next.ps1 -Mode live' -ForegroundColor Green
