import requests

url = "https://www.sbito.co.th/Research_Detail.aspx?id=18972"
try:
    response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}, timeout=15)
    print(f"Status Code: {response.status_code}")
    print(f"Content Length: {len(response.content)}")
    print(f"Text length: {len(response.text)}")
    print("Snippet:")
    print(response.text[:1000])
except Exception as e:
    print(f"Error: {e}")
