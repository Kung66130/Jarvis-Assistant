import google.generativeai as genai
import os
from jarvis_runtime import get_env_value

api_key = get_env_value("GEMINI_API_KEY", allow_legacy_config=True)
genai.configure(api_key=api_key)

try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(m.name)
except Exception as e:
    print(f"Error: {e}")
