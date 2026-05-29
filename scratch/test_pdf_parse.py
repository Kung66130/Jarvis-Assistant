import requests
import re
import io
import PyPDF2

url_detail = "https://www.sbito.co.th/Research_Detail.aspx?id=18972"
try:
    response = requests.get(url_detail, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
    match = re.search(r'url=(.*\.pdf)', response.text, re.IGNORECASE)
    if match:
        pdf_relative_url = match.group(1)
        pdf_url = f"https://www.sbito.co.th/{pdf_relative_url}"
        print(f"Downloading PDF from: {pdf_url}")
        
        pdf_response = requests.get(pdf_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        print(f"PDF download status: {pdf_response.status_code}, Length: {len(pdf_response.content)}")
        
        # Parse PDF
        with io.BytesIO(pdf_response.content) as f:
            reader = PyPDF2.PdfReader(f)
            text = ""
            for page_idx, page in enumerate(reader.pages):
                text += f"\n--- Page {page_idx + 1} ---\n"
                text += page.extract_text() + "\n"
            
            print(f"Extracted {len(text)} characters.")
            print("First 1000 characters:")
            print(text[:1000])
            
            # ลองหาหัวข้อ "ประเด็นที่น่าติดตาม" หรือ "Interesting Issues"
            # หาตำแหน่ง Interesting Issues
            issues_idx = text.lower().find("interesting issues")
            if issues_idx != -1:
                print("\n--- FOUND INTERESTING ISSUES ---")
                # พิมพ์ข้อความหลังจาก Interesting Issues สัก 2000 ตัวอักษร
                print(text[issues_idx:issues_idx+2000])
            else:
                print("Could not find 'Interesting Issues' in text.")
    else:
        print("No PDF redirect link found.")
except Exception as e:
    print(f"Error: {e}")
