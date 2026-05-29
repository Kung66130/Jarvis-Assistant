import requests
import re
from bs4 import BeautifulSoup

url = "https://www.sbito.co.th/Research.aspx"
try:
    response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, 'html.parser')
    links = soup.find_all('a', href=True)
    pdf_links = []
    for link in links:
        href = link['href']
        text = link.get_text().strip()
        if '.pdf' in href.lower() or 'morning' in href.lower() or 'morning' in text.lower():
            pdf_links.append((text, href))
            
    print(f"Found {len(pdf_links)} relevant links:")
    for idx, (txt, href) in enumerate(pdf_links[:15]):
        print(f"{idx+1}. {txt} -> {href}")
except Exception as e:
    print(f"Error: {e}")
