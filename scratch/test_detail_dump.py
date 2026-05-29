import requests
from bs4 import BeautifulSoup

url = "https://www.sbito.co.th/Research_Detail.aspx?id=18972"
try:
    response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # print text ใน body
    text = soup.get_text()
    print("--- Page Text Snippet ---")
    print(text[:2000])
    
    # print all iframes
    print("--- Iframes ---")
    for iframe in soup.find_all('iframe'):
        print(iframe)
        
    # print all links with target or href
    print("--- All Links ---")
    for a in soup.find_all('a', href=True)[:30]:
        print(f"{a.get_text().strip()} -> {a['href']}")
        
except Exception as e:
    print(f"Error: {e}")
