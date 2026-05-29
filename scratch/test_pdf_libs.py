import requests
import re
import io
import os
import sys

# Test different PDF extraction methods on SBITO PDF
url_detail = "https://www.sbito.co.th/Research_Detail.aspx?id=18958"
try:
    response = requests.get(url_detail, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
    match = re.search(r'url=(.*\.pdf)', response.text, re.IGNORECASE)
    if match:
        pdf_relative_url = match.group(1)
        pdf_url = f"https://www.sbito.co.th/{pdf_relative_url}"
        print(f"Downloading PDF from: {pdf_url}")
        
        pdf_response = requests.get(pdf_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        pdf_bytes = pdf_response.content
        
        # Test 1: Try PyPDF2 but extracting with different encodings if possible
        print("Testing PyPDF2 with raw text decoding...")
        import PyPDF2
        with io.BytesIO(pdf_bytes) as f:
            reader = PyPDF2.PdfReader(f)
            # Try to see what PyPDF2 gives us
            first_page_text = reader.pages[0].extract_text()
            print("PyPDF2 default output snippet:")
            print(first_page_text[:300].encode('utf-8', errors='replace').decode('utf-8'))
            
            # Let's try to inspect PyPDF2 encoding extraction
            # Sometimes characters are in custom fonts.
            
        # Test 2: Check if pdfplumber is available
        try:
            print("\nTesting pdfplumber...")
            import pdfplumber
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                first_page = pdf.pages[0]
                text = first_page.extract_text()
                print("pdfplumber output snippet:")
                print(text[:300])
        except ImportError:
            print("pdfplumber not installed.")
            
        # Test 3: Check if fitz (PyMuPDF) is available
        try:
            print("\nTesting PyMuPDF (fitz)...")
            import fitz
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            text = doc[0].get_text()
            print("PyMuPDF output snippet:")
            print(text[:300])
        except ImportError:
            print("PyMuPDF (fitz) not installed.")

except Exception as e:
    print(f"Error: {e}")
