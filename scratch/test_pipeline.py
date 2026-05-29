import io
import os
import re
import sys
import json
import requests
from bs4 import BeautifulSoup
import PyPDF2

# Add parent directory to sys.path to find jarvis_runtime
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from jarvis_runtime import get_env_value
import google.generativeai as genai

def despace(text):
    # Matches sequences of (Thai char + space) and joins them
    def replacer(match):
        return match.group(0).replace(" ", "")
    
    thai_char_pattern = r'[\u0E00-\u0E7F]\s(?=[\u0E00-\u0E7F])'
    text = re.sub(thai_char_pattern, lambda m: m.group(0)[0], text)
    return text

def test_pipeline():
    print("Step 1: Fetching SBITO Research Page...")
    list_url = "https://www.sbito.co.th/Research.aspx"
    response = requests.get(list_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find latest Morning Brief
    brief_link = None
    for link in soup.find_all('a', href=True):
        href = link['href']
        text = link.get_text().strip()
        if 'Morning Brief' in text and 'Research_Detail.aspx' in href:
            brief_link = (text, href)
            break
            
    if not brief_link:
        print("Error: Could not find any Morning Brief link.")
        return
        
    title, relative_href = brief_link
    detail_url = f"https://www.sbito.co.th/{relative_href}"
    print(f"Latest Morning Brief: '{title}' -> {detail_url}")
    
    print("Step 2: Fetching Detail Page for PDF redirect...")
    detail_response = requests.get(detail_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
    match = re.search(r'url=(.*\.pdf)', detail_response.text, re.IGNORECASE)
    if not match:
        print("Error: Could not find PDF redirect URL.")
        return
        
    pdf_relative_url = match.group(1)
    pdf_url = f"https://www.sbito.co.th/{pdf_relative_url}"
    print(f"Found PDF URL: {pdf_url}")
    
    print("Step 3: Downloading PDF...")
    pdf_response = requests.get(pdf_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
    pdf_bytes = pdf_response.content
    print(f"Downloaded {len(pdf_bytes)} bytes.")
    
    print("Step 4: Extracting text using PyPDF2 & Despacing...")
    with io.BytesIO(pdf_bytes) as f:
        reader = PyPDF2.PdfReader(f)
        raw_text = ""
        for i, page in enumerate(reader.pages):
            raw_text += f"\n--- Page {i+1} ---\n"
            raw_text += page.extract_text() + "\n"
            
    cleaned_text = despace(raw_text)
    print(f"Raw Text Len: {len(raw_text)}, Cleaned Text Len: {len(cleaned_text)}")
    
    print("Step 5: Invoking Gemini API...")
    api_key = get_env_value("GEMINI_API_KEY", allow_legacy_config=True)
    if not api_key:
        print("Error: GEMINI_API_KEY not found.")
        return
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-flash-latest")
    
    prompt = f"""
คุณคือ Jarvis (Full-Text Reader) ผู้ช่วยของบอส
ภารกิจ: สกัดเนื้อหาภายใต้หัวข้อ "ประเด็นที่น่าติดตาม" หรือ "Interesting Issues" จากบทวิเคราะห์ Morning Brief ภาษาไทยด้านล่างนี้
กติกาที่ต้องปฏิบัติตามอย่างเคร่งครัด:
1. ให้ดึงข้อความภาษาไทยทั้งหมดที่อยู่ภายใต้หัวข้อ "ประเด็นที่น่าติดตาม" หรือ "Interesting Issues" (รวมหัวข้อย่อยและเนื้อหาทั้งหมดในส่วนนั้น)
2. **ห้ามย่อ ห้ามสรุป** ให้ดึงเนื้อหาออกมาคำต่อคำตรงตามตัวอักษรให้ครบถ้วนสมบูรณ์ที่สุด ห้ามตัดทอนประโยคเด็ดขาด
3. หากมีคำแปลกๆ หรือสะกดผิด หรือเว้นวรรคแปลกๆ ให้แก้ไขให้อ่านง่ายเป็นธรรมชาติสำหรับภาษาไทย
4. ห้ามมีคำนำหรือคำอธิบายประกอบใดๆ ให้ตอบเฉพาะ JSON ตามโครงสร้างด้านล่างนี้เท่านั้น

ตอบกลับในรูปแบบ JSON นี้เท่านั้น:
{{
  "text": "เนื้อหาทั้งหมดที่สกัดมาคำต่อคำจากส่วนประเด็นที่น่าติดตาม...",
  "tone": "serious",
  "voice": "niwat"
}}

เนื้อหาบทวิเคราะห์:
{cleaned_text}
"""
    response = model.generate_content(prompt, generation_config={"temperature": 0.2})
    raw_response = response.text.strip()
    print("Gemini Raw Response:")
    print(raw_response)
    
    try:
        cleaned = raw_response
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
        payload = json.loads(cleaned)
        print("\nParsed JSON successfully!")
        print(f"Tone: {payload.get('tone')}")
        print(f"Voice: {payload.get('voice')}")
        print(f"Text Length: {len(payload.get('text', ''))}")
        print("Sample Text:")
        print(payload.get('text', '')[:500])
    except Exception as e:
        print(f"JSON Parsing Error: {e}")

if __name__ == "__main__":
    test_pipeline()
