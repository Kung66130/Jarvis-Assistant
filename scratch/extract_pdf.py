import io
import requests
import PyPDF2

url = "https://www.sbito.co.th/upload/Mornin_1778811758_96487.pdf"
print(f"Downloading PDF: {url}")
try:
    response = requests.get(url, timeout=30)
    with io.BytesIO(response.content) as f:
        reader = PyPDF2.PdfReader(f)
        text = ""
        for i, page in enumerate(reader.pages):
            text += f"--- Page {i+1} ---\n"
            text += page.extract_text() + "\n"
        
        with open("morning_brief_full.txt", "w", encoding="utf-8") as out:
            out.write(text)
    print("PDF extracted successfully to morning_brief_full.txt")
except Exception as e:
    print(f"Error: {e}")
