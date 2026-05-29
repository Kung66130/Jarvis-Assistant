import sys
import os
import json
import time

sys.path.append(r"C:\Project\Jarvis-Hermes Assistant")
from listen import pop_telegram_command
from jarvis_loop import send_to_telegram

print("1. Testing send_to_jarvis simulation...")
cmd_file = r"C:\Project\Jarvis-Hermes Assistant\telegram_cmd.json"
data = {"command": "แนะนำตัวหน่อย", "timestamp": time.time()}
with open(cmd_file, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False)
print("Simulation success")

print("2. Testing listen.py detection...")
tg_cmd_raw = pop_telegram_command()
print(f"Popped command: {tg_cmd_raw}")

if tg_cmd_raw:
    tg_data = json.loads(tg_cmd_raw)
    command = tg_data.get("command")
    print(f"3. Testing jarvis_loop processing for command: {command}")
    
    # We will just test the brain directly to avoid speaker / pyaudio issues in headless env
    try:
        from brain import get_ai_response
        print("Sending to brain...")
        payload = get_ai_response(command)
        
        print("4. Testing send_to_telegram...")
        if isinstance(payload, dict):
            reply_text = payload.get("reply_text", "")
            send_to_telegram(reply_text)
            
            # Check if telegram_resp.json exists
            resp_file = r"C:\Project\Jarvis-Hermes Assistant\telegram_resp.json"
            if os.path.exists(resp_file):
                with open(resp_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    print(f"SUCCESS: Found reply in telegram_resp.json: {data.get('reply_text')}")
                os.remove(resp_file)
            else:
                print("ERROR: telegram_resp.json not found")
        else:
            print(f"Payload is not dict: {payload}")
    except Exception as e:
        print(f"Brain exception: {e}")
else:
    print("ERROR: Could not pop command")
