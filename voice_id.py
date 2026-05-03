import sys
import os

# ปิด Warning รกๆ ของ HuggingFace
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

# เพิ่ม Path สำหรับไลบรารีที่ลงแบบ --user
user_site = os.path.expandvars(r'%APPDATA%\Python\Python312\site-packages')
if user_site not in sys.path:
    sys.path.append(user_site)

import pathlib
import shutil
import sounddevice as sd
import soundfile as sf
import time

# แฮ็กระบบ Windows เพื่อแก้ปัญหา WinError 1314 (Symlink Privilege)
def patched_symlink_to(self, target, target_is_directory=False):
    try:
        shutil.copy2(target, self)
    except Exception as e:
        print(f"Copy fallback failed: {e}")

pathlib.Path.symlink_to = patched_symlink_to

FS = 16000  # Sample rate ที่ AI โมเดลต้องการ
DURATION = 5  # เวลาอัดเสียง (วินาที)
BOSS_FILE = os.path.join(os.path.dirname(__file__), "boss_voice.wav")
TEMP_FILE = os.path.join(os.path.dirname(__file__), "temp_voice.wav")

def record_audio(filename, duration=DURATION):
    print(f"\n🎤 กำลังเตรียมไมโครโฟน...")
    time.sleep(1)
    print(f"🔴 เริ่มบันทึกเสียง ({duration} วินาที)... กรุณาพูดได้เลยครับ!")
    recording = sd.rec(int(duration * FS), samplerate=FS, channels=1, dtype='float32')
    sd.wait()
    print(f"✅ บันทึกเสร็จสิ้น!")
    sf.write(filename, recording, FS)
    return filename

def enroll():
    print("=== ระบบลงทะเบียนลายนิ้วมือเสียง (Voice Print) ===")
    print("กรุณาพูดแนะนำตัวหรือพูดอะไรก็ได้ เพื่อให้จาร์วิสจดจำเสียงของคุณ (5 วินาที)")
    record_audio(BOSS_FILE, duration=5)
    print(f"\n🎉 บันทึกเสียงต้นแบบของบอสสำเร็จแล้ว!")

def verify():
    if not os.path.exists(BOSS_FILE):
        print("⚠️ ยังไม่มีเสียงต้นแบบ กรุณารันคำสั่งลงทะเบียนก่อนครับ")
        return

    print("=== ระบบยืนยันตัวตน (Speaker Verification) ===")
    print("กรุณาพูดเพื่อยืนยันตัวตน (3 วินาที)")
    record_audio(TEMP_FILE, duration=3)

    print("\n🧠 กำลังวิเคราะห์ลายนิ้วมือเสียงด้วย AI (SpeechBrain)...")
    import logging
    logging.getLogger("speechbrain").setLevel(logging.ERROR) # ปิด Log รกๆ
    
    from speechbrain.inference.speaker import SpeakerRecognition
    
    # โหลด AI Model แบบ State-of-the-art (ครั้งแรกจะโหลดโมเดลจากเน็ตประมาณ 80MB)
    verification = SpeakerRecognition.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb", 
        savedir="pretrained_models/spkrec-ecapa-voxceleb"
    )
    
    import torch
    import soundfile as sf
    
    # แก้บั๊กการโหลดไฟล์เสียง (ข้าม k2 และ torchcodec) โดยใช้ soundfile พื้นฐานที่เสถียรกว่า
    data_x, _ = sf.read(BOSS_FILE)
    waveform_x = torch.tensor(data_x).unsqueeze(0).float()
    
    data_y, _ = sf.read(TEMP_FILE)
    waveform_y = torch.tensor(data_y).unsqueeze(0).float()
    
    # Speechbrain ต้องการ (batch, time) แต่ torchaudio ให้ (channels, time) ซึ่งใช้แทนกันได้ถ้าเป็น mono
    score, prediction = verification.verify_batch(waveform_x, waveform_y)
    
    # แปลง Tensor เป็นค่าตัวเลขธรรมดา
    score_val = score[0].item() if hasattr(score, 'item') else score.item()
    pred_val = prediction[0].item() if hasattr(prediction, 'item') else prediction.item()
    
    print("\n" + "="*30)
    print(f"ความเหมือน (Score): {score_val:.4f}")
    print("="*30)
    
    if pred_val or score_val > 0.25:  
        print("✅ ยืนยันตัวตนสำเร็จ: ยินดีต้อนรับครับบอส!")
    else:
        print("❌ ยืนยันตัวตนล้มเหลว: ตรวจพบผู้บุกรุก! เสียงไม่ตรงกับบอส")

def verify_file(filepath, threshold=0.25):
    """ฟังก์ชันสำหรับให้ script อื่นเรียกใช้ โดยจะไม่ print ออกมาให้รก (คืนค่า True/False)"""
    if not os.path.exists(BOSS_FILE):
        return True  # ถ้ายังไม่ลงทะเบียนบอส ปล่อยผ่านไปก่อน

    import logging
    logging.getLogger("speechbrain").setLevel(logging.ERROR)
    
    from speechbrain.inference.speaker import SpeakerRecognition
    import torch
    import soundfile as sf
    
    # ซ่อน output 
    old_stdout = sys.stdout
    sys.stdout = open(os.devnull, 'w')
    try:
        verification = SpeakerRecognition.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb", 
            savedir=os.path.join(os.path.dirname(__file__), "pretrained_models/spkrec-ecapa-voxceleb")
        )
        data_x, _ = sf.read(BOSS_FILE)
        waveform_x = torch.tensor(data_x).unsqueeze(0).float()
        
        data_y, _ = sf.read(filepath)
        waveform_y = torch.tensor(data_y).unsqueeze(0).float()
        
        score, prediction = verification.verify_batch(waveform_x, waveform_y)
        score_val = score[0].item() if hasattr(score, 'item') else score.item()
        pred_val = prediction[0].item() if hasattr(prediction, 'item') else prediction.item()
        
        return pred_val or score_val > threshold
    finally:
        sys.stdout = old_stdout

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--enroll":
        enroll()
    elif len(sys.argv) > 1 and sys.argv[1] == "--verify":
        verify()
    else:
        print("การใช้งาน:")
        print("  py voice_id.py --enroll  (เพื่อบันทึกเสียงบอสครั้งแรก)")
        print("  py voice_id.py --verify  (เพื่อทดสอบการจำเสียง)")
