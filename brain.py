import google.generativeai as genai
import json
import os
import sys
import io

# บังคับให้ Output เป็น UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# โหลด API Key
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
with open(CONFIG_PATH, "r") as f:
    config = json.load(f)

genai.configure(api_key=config["GEMINI_API_KEY"])

# ตั้งค่าโมเดล
model = genai.GenerativeModel('gemini-1.5-flash')

def get_ai_response(prompt):
    try:
        # กำหนดบุคลิกให้จาวิส
        system_instruction = "คุณคือ Jarvis ผู้ช่วย AI อัจฉริยะของ 'บอส' (Boss) ตอบคำถามให้กระชับ เป็นกันเอง แต่สุภาพ และพร้อมช่วยเหลือเสมอ"
        full_prompt = f"{system_instruction}\n\nคำสั่งจากบอส: {prompt}"
        
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        return f"ขออภัยครับบอส เกิดข้อผิดพลาดในระบบสมอง: {str(e)}"

if __name__ == "__main__":
    args = sys.argv[1:]
    if args:
        user_input = " ".join(args)
        print(get_ai_response(user_input))
    else:
        print("ต้องการคำสั่งเพื่อประมวลผลครับบอส")
