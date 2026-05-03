import asyncio
import edge_tts
import os
import subprocess

async def speak():
    text = "สวัสดีค่ะ ฉันคือเปรมวดี โทนเสียงผู้หญิงที่นุ่มนวลและอ่อนหวานค่ะ คุณได้ยินเสียงฉันชัดเจนไหมคะ?"
    voice = "th-TH-PremwadeeNeural"
    output_file = "temp_female.mp3"
    
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)
    
    play_cmd = f'powershell -Command "Add-Type -AssemblyName presentationCore; $p = New-Object system.windows.media.mediaplayer; $p.open(\'{os.path.abspath(output_file)}\'); $p.Play(); Start-Sleep -Seconds 10"'
    subprocess.run(play_cmd, shell=True)

if __name__ == "__main__":
    asyncio.run(speak())
