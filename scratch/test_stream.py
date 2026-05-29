import os
import google.generativeai as genai
import time

key = os.environ.get("GEMINI_API_KEY", "")
genai.configure(api_key=key)

try:
    print("Testing streaming with gemini-flash-latest...")
    model = genai.GenerativeModel("gemini-flash-latest")
    response = model.generate_content("Write a short poem about coding.", stream=True)
    start_time = time.time()
    for chunk in response:
        print(f"Chunk ({time.time() - start_time:.2f}s): {chunk.text}")
    print("Streaming success!")
except Exception as e:
    print("Streaming failed:", e)
