import requests
import re
import os
import sys

# Add parent directory to sys.path to find jarvis_runtime
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from jarvis_runtime import get_env_value
import google.generativeai as genai

# Configure Gemini
api_key = get_env_value("GEMINI_API_KEY", allow_legacy_config=True)
genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-2.0-flash")

url_detail = "https://www.sbito.co.th/Research_Detail.aspx?id=18958" # 15 May 2026
try:
    response = requests.get(url_detail, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
    match = re.search(r'url=(.*\.pdf)', response.text, re.IGNORECASE)
    if match:
        pdf_relative_url = match.group(1)
        pdf_url = f"https://www.sbito.co.th/{pdf_relative_url}"
        print(f"Downloading PDF from: {pdf_url}")
        
        pdf_response = requests.get(pdf_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        pdf_data = pdf_response.content
        
        # Save temp file
        temp_pdf_path = "scratch/temp_morning.pdf"
        with open(temp_pdf_path, "wb") as f:
            f.write(pdf_data)
            
        print("Uploading PDF to Gemini...")
        gemini_file = genai.upload_file(path=temp_pdf_path, mime_type="application/pdf")
        print(f"Uploaded file: {gemini_file.name}")
        
        prompt = """
        คุณคือ Jarvis ผู้ช่วยดึงข้อมูลบทวิเคราะห์หุ้น
        จากไฟล์ PDF Morning Brief ของ SBITO ที่แนบมานี้
        กรุณาดึงเนื้อหาทั้งหมดภายใต้หัวข้อ "ประเด็นที่น่าติดตาม" หรือ "Interesting Issues" (รวมหัวข้อย่อยและเนื้อหาทั้งหมดในส่วนนั้น)
        โดยห้ามย่อ ห้ามสรุป ให้ดึงเนื้อความภาษาไทยออกมาคำต่อคำตรงตัวอักษรให้ครบถ้วนสมบูรณ์ที่สุด
        """
        
        print("Generating content from Gemini...")
        gemini_response = model.generate_content([gemini_file, prompt])
        print("\n--- GEMINI EXTRACTED CONTENT ---")
        print(gemini_response.text)
        
        # Clean up gemini file
        genai.delete_file(gemini_file.name)
        os.remove(temp_pdf_path)
    else:
        print("No PDF redirect link found.")
except Exception as e:
    print(f"Error: {e}")
