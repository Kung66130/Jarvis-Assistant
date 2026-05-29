import requests
from bs4 import BeautifulSoup

url = "https://www.sbito.co.th/Research_Detail.aspx?id=18972"
try:
    response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # ดู a href ทั้งหมดในหน้ารายละเอียด เพื่อหาลิงก์ PDF ของ Morning Brief
    pdf_links = []
    for link in soup.find_all('a', href=True):
        href = link['href']
        text = link.get_text().strip()
        if '.pdf' in href.lower():
            pdf_links.append((text, href))
            
    print("Found PDF links in Detail page:")
    for txt, href in pdf_links:
        print(f"Text: {txt} -> Link: {href}")
        
except Exception as e:
    print(f"Error: {e}")
