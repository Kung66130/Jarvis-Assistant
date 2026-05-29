import os
import google.generativeai as genai

key = os.environ.get("GEMINI_API_KEY", "")
print("Testing key:", key[:15] + "...")

try:
    genai.configure(api_key=key)
    # Test gemini-2.0-flash
    print("Testing gemini-2.0-flash...")
    model = genai.GenerativeModel("gemini-2.0-flash")
    res = model.generate_content("Hello. Reply with OK.")
    print("gemini-2.0-flash success:", res.text)
except Exception as e:
    print("gemini-2.0-flash failed:", e)

try:
    # Test gemini-1.5-flash
    print("Testing gemini-1.5-flash...")
    model = genai.GenerativeModel("gemini-1.5-flash")
    res = model.generate_content("Hello. Reply with OK.")
    print("gemini-1.5-flash success:", res.text)
except Exception as e:
    print("gemini-1.5-flash failed:", e)

try:
    # Test gemini-flash-latest
    print("Testing gemini-flash-latest...")
    model = genai.GenerativeModel("gemini-flash-latest")
    res = model.generate_content("Hello. Reply with OK.")
    print("gemini-flash-latest success:", res.text)
except Exception as e:
    print("gemini-flash-latest failed:", e)
