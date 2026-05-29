import requests
import re
import io
import PyPDF2

url_detail = "https://www.sbito.co.th/Research_Detail.aspx?id=18958"
try:
    response = requests.get(url_detail, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
    match = re.search(r'url=(.*\.pdf)', response.text, re.IGNORECASE)
    if match:
        pdf_relative_url = match.group(1)
        pdf_url = f"https://www.sbito.co.th/{pdf_relative_url}"
        print(f"Downloading PDF from: {pdf_url}")
        
        pdf_response = requests.get(pdf_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        
        with io.BytesIO(pdf_response.content) as f:
            reader = PyPDF2.PdfReader(f)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            
            print("First 500 characters of May 15 PDF:")
            print(text[:500])
except Exception as e:
    print(f"Error: {e}")
