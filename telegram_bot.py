import os
import json
import time
import telebot
from pathlib import Path

# Load env safely
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

APP_DIR = Path(__file__).resolve().parent
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

if not TOKEN or TOKEN == "put-your-telegram-bot-token-here":
    print("Error: TELEGRAM_BOT_TOKEN is not set. Please check your .env file.")
    exit(1)

bot = telebot.TeleBot(TOKEN)
print("Telegram Bot is running... Press Ctrl+C to stop.")

def send_to_jarvis(command: str, chat_id: int):
    cmd_file = APP_DIR / "telegram_cmd.json"
    data = {"command": command, "chat_id": chat_id, "timestamp": time.time()}
    try:
        with open(cmd_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error writing to cmd file: {e}")
        return False

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "สวัสดีครับบอส ผมคือระบบรับคำสั่งของ Jarvis พิมพ์ข้อความคำสั่งทิ้งไว้ได้เลยครับ")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    command = message.text
    chat_id = message.chat.id
    print(f"Received command: {command} from chat: {chat_id}")
    
    # Send command to Jarvis with chat_id
    if not send_to_jarvis(command, chat_id):
        bot.send_message(chat_id, "⚠️ เกิดข้อผิดพลาดในการส่งคำสั่งไปที่ Jarvis ครับ")

# Background thread to check for responses asynchronously
def poll_responses():
    resp_file = APP_DIR / "telegram_resp.json"
    import threading
    while True:
        if resp_file.exists():
            try:
                # Give a tiny moment for write to finish
                time.sleep(0.1)
                with open(resp_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                chat_id = data.get("chat_id")
                reply_text = data.get("reply_text", "")
                photo_path = data.get("photo_path")
                
                if chat_id and (reply_text or photo_path):
                    if photo_path and os.path.exists(photo_path):
                        with open(photo_path, 'rb') as photo:
                            # If text is too long for caption, send separately
                            if len(reply_text) <= 1024:
                                bot.send_photo(chat_id, photo, caption=reply_text)
                            else:
                                bot.send_photo(chat_id, photo)
                                bot.send_message(chat_id, reply_text, parse_mode="Markdown")
                    else:
                        bot.send_message(chat_id, reply_text, parse_mode="Markdown")
                    print(f"Sent response to chat {chat_id}")
                
                resp_file.unlink(missing_ok=True)
            except json.JSONDecodeError:
                pass # File is still being written
            except Exception as e:
                print(f"Error processing response file: {e}")
                resp_file.unlink(missing_ok=True)
        time.sleep(0.5)

import threading
threading.Thread(target=poll_responses, daemon=True).start()

# Polling with exception handling
while True:
    try:
        bot.polling(none_stop=True, timeout=60)
    except Exception as e:
        print(f"Connection error: {e}")
        time.sleep(5)
