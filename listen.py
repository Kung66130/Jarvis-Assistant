import speech_recognition as sr
import sys
import io
import time
import wave
import os
import tempfile
import pyaudio
import numpy as np

# บังคับให้ Output เป็น UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def listen_wake_word():
    CHUNK = 1280
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000
    
    # 1. โหลดโมเดล Wake Word "จาร์วิส" (ออฟไลน์ 100%)
    import openwakeword
    from openwakeword.model import Model
    print("Loading Wake Word Model...")
    owwModel = Model(wakeword_models=["jarvis"])
    
    p = pyaudio.PyAudio()
    
    # ── 1. ระบบรักษาความปลอดภัย: ล็อกให้ฟังผ่านหูฟังบอสเท่านั้น ──
    device_index = None
    for i in range(p.get_device_count()):
        dev_info = p.get_device_info_by_index(i)
        name = dev_info.get('name', '')
        if dev_info.get('maxInputChannels') > 0 and "EDIFIER" in name.upper():
            if "HANDS-FREE" in name.upper():
                device_index = i
                break
            device_index = i
            
    if device_index is None:
        print("\n🔒 [ระบบรักษาความปลอดภัย] ไม่พบหูฟังบลูทูธ (EDIFIER X5 Pro) จาร์วิสระงับการฟังเสียงครับ...")
        p.terminate()
        time.sleep(3)
        return ""
        
    print(f"\n🎧 [โหมดไร้สัมผัส] ยืนยันหูฟังบอส (ID: {device_index}) กำลังเตรียมไมโครโฟน...")
    
    # ลองสุ่ม Sample Rate ที่บลูทูธยอมรับ (16k, 44.1k, 48k, 8k)
    stream = None
    actual_rate = RATE
    for test_rate in [16000, 44100, 48000, 8000]:
        try:
            stream = p.open(format=FORMAT, channels=CHANNELS, rate=test_rate, input=True, input_device_index=device_index, frames_per_buffer=CHUNK)
            actual_rate = test_rate
            break
        except Exception:
            continue
            
    if stream is None:
        print("❌ หูฟังปฏิเสธการเชื่อมต่อไมโครโฟน (ลองปิด-เปิดบลูทูธใหม่ดูครับ)")
        p.terminate()
        return ""

    print(f"✅ เชื่อมต่อไมค์สำเร็จที่ {actual_rate}Hz พูดว่า 'จาร์วิส' เพื่อเริ่มงาน")
    state_file = os.path.join(os.path.dirname(__file__), "state.txt")
    with open(state_file, "w", encoding="utf-8") as f: f.write("AWAITING")

    jarvis_woke = False
    while not jarvis_woke:
        try:
            data = stream.read(CHUNK, exception_on_overflow=False)
            audio_data = np.frombuffer(data, dtype=np.int16)
            prediction = owwModel.predict(audio_data)
            
            for md_name in prediction.keys():
                if prediction[md_name] > 0.3:
                    jarvis_woke = True
                    break
        except Exception as e:
            print(f"Stream Error: {e}")
            break
                
    if not jarvis_woke:
        stream.close()
        p.terminate()
        return ""

    print("\n🟢 จาร์วิสตื่นแล้ว! กำลังบันทึกคำสั่ง...")
    with open(state_file, "w", encoding="utf-8") as f: f.write("LISTENING")
    
    # ปิดไมค์สตรีมเก่า เพื่อให้ Recognizer ใช้ไมค์ได้
    stream.stop_stream()
    stream.close()
    p.terminate()
    
    # 2. เริ่มอัดเสียงคำสั่งจริงๆ (ตัดจบอัตโนมัติเมื่อหยุดพูด)
    r = sr.Recognizer()
    with sr.Microphone(device_index=device_index, sample_rate=actual_rate) as source:
        try:
            r.adjust_for_ambient_noise(source, duration=0.5)
            audio = r.listen(source, timeout=5, phrase_time_limit=10)
        except sr.WaitTimeoutError:
            print("ไม่ได้ยินคำสั่ง กลับไปนอนต่อ...")
            return ""
            
    print("✅ บันทึกคำสั่งเสร็จสิ้น กำลังประมวลผล...")
    with open(state_file, "w", encoding="utf-8") as f: f.write("THINKING")
    
    # บันทึกลงไฟล์ชั่วคราว
    temp_wav = os.path.join(tempfile.gettempdir(), "ptt_voice.wav")
    with open(temp_wav, "wb") as f:
        f.write(audio.get_wav_data())
    
    # ── 3. Speech to Text (ข้าม Voice ID เพราะล็อกหูฟังบอสไว้แล้ว) ──
    try:
        text = r.recognize_google(audio, language="th-TH")
        return text
    except Exception:
        return ""

if __name__ == "__main__":
    result = listen_wake_word()
    if result:
        print(f"RESULT:{result}")
    else:
        print("RESULT:NONE")
