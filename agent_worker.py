import io
import json
import os
import sys
import time
import requests
import re
import subprocess
from bs4 import BeautifulSoup
import PyPDF2
from report_renderer import render_report_card

try:
    import google.generativeai as genai
except ImportError:
    genai = None

from jarvis_runtime import get_env_value

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

MODEL_NAME = "gemini-2.5-flash" # Stable Quota Slow Brain Agent
QUEUE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_queue.json")

def configure_model():
    if genai is None:
        raise RuntimeError("Missing google.generativeai")
    api_key = get_env_value("GEMINI_API_KEY", allow_legacy_config=True)
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(MODEL_NAME)

def fetch_content(url: str) -> str:
    print(f"Fetching: {url}")
    try:
        # Check if PDF
        if url.lower().endswith('.pdf') or 'pdf' in url.lower():
            response = requests.get(url, timeout=15)
            with io.BytesIO(response.content) as f:
                reader = PyPDF2.PdfReader(f)
                text = ""
                for page in reader.pages[:10]: # Limit to first 10 pages
                    text += page.extract_text() + "\n"
                return text[:100000]
        
        # Web Scraping
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        response.encoding = response.apparent_encoding # Fix Thai encoding issues
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove noise
        for s in soup(['script', 'style', 'nav', 'header', 'footer']):
            s.decompose()
            
        text = soup.get_text(separator=' ')
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:100000]
    except Exception as e:
        print(f"Fetch error: {e}")
        return f"Error fetching content: {e}"

def search_web(query: str) -> str:
    """Searches the web for the given query using DuckDuckGo HTML search and returns top results with titles, links, and snippets."""
    print(f"Searching web for: {query}")
    url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return f"Error: Search request failed with status code {response.status_code}"
        
        soup = BeautifulSoup(response.text, 'html.parser')
        results = []
        for body in soup.find_all('div', class_='result__body')[:5]:
            title_a = body.find('a', class_='result__url')
            snippet_a = body.find('a', class_='result__snippet')
            if title_a and snippet_a:
                title = title_a.get_text().strip()
                link = title_a['href']
                snippet = snippet_a.get_text().strip()
                results.append(f"Title: {title}\nLink: {link}\nSnippet: {snippet}\n---")
                
        if not results:
            return "No search results found."
        return "\n".join(results)
    except Exception as e:
        print(f"Search error: {e}")
        return f"Search error: {e}"

def despace(text):
    # Matches sequences of (Thai char + space) and joins them
    thai_char_pattern = r'[\u0E00-\u0E7F]\s(?=[\u0E00-\u0E7F])'
    text = re.sub(thai_char_pattern, lambda m: m.group(0)[0], text)
    return text

def fetch_morning_brief_pdf(target_date: str = None) -> tuple[str, str]:
    list_url = "https://www.sbito.co.th/Research.aspx"
    response = requests.get(list_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, 'html.parser')
    
    brief_link = None
    for link in soup.find_all('a', href=True):
        href = link['href']
        text = link.get_text().strip()
        if 'Morning Brief' in text and 'Research_Detail.aspx' in href:
            if target_date:
                if target_date.lower() in text.lower():
                    brief_link = (text, href)
                    break
            else:
                brief_link = (text, href)
                break
                
    if not brief_link and target_date:
        for link in soup.find_all('a', href=True):
            href = link['href']
            text = link.get_text().strip()
            if 'Morning Brief' in text and 'Research_Detail.aspx' in href:
                brief_link = (text, href)
                break
                
    if not brief_link:
        raise RuntimeError("No Morning Brief link found on SBITO site.")
        
    title, relative_href = brief_link
    detail_url = f"https://www.sbito.co.th/{relative_href}"
    
    detail_response = requests.get(detail_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
    match = re.search(r'url=(.*\.pdf)', detail_response.text, re.IGNORECASE)
    if not match:
        raise RuntimeError(f"Could not find PDF redirect URL on SBITO detail page {detail_url}")
        
    pdf_relative_url = match.group(1)
    pdf_url = f"https://www.sbito.co.th/{pdf_relative_url}"
    return title, pdf_url

# --- Coding Agent Tools ---
def read_file(path: str) -> str:
    """Reads a file from the local filesystem."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()[:50000]
    except Exception as e:
        return f"Error: {e}"

def write_file(path: str, content: str) -> str:
    """Writes content to a file in the local filesystem."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return "File written successfully."
    except Exception as e:
        return f"Error: {e}"

def run_cmd(command: str) -> str:
    """Runs a shell command and returns the standard output and error."""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=60)
        out = (result.stdout + "\n" + result.stderr).strip()
        return out[:50000] if out else "Command executed successfully with no output."
    except Exception as e:
        return f"Error: {e}"
# -------------------------

def run_agent(action_json: str):
    try:
        action = json.loads(action_json)
        action_type = action.get("type")
        
        if action_type == "fetch_web":
            url = action.get("url")
            if not url:
                raise ValueError("No URL provided")
                
            content = fetch_content(url)
            model = configure_model()
            
            prompt = f"""
คุณคือ Jarvis (Full-Text Reader)
ภารกิจ: อ่านบทความที่ดึงมาได้ให้บอสฟัง "ทุกตัวอักษร" โดยห้ามสรุปหรือตัดทอนเนื้อหาหลัก

เว็บไซต์/ไฟล์: {url}
เนื้อหาดิบที่ดึงมาได้:
{content[:90000]}

คำสั่ง:
1. นำเนื้อหาหลักจากบทความมาเรียงต่อกันให้เป็นบทอ่านที่สมบูรณ์
2. **ห้ามสรุป ห้ามย่อ** ให้คงไว้ทุกคำพูดที่ผู้เขียนเขียนมา เพราะผู้เขียนสรุปมาดีอยู่แล้ว
3. ตัดเฉพาะขยะที่ติดมา (เช่น เลขหน้า, ปุ่มกด, เมนูข้างเคียง) ออกเท่านั้น
4. จัดรูปแบบเว้นวรรคให้เหมาะกับการอ่านออกเสียงของ AI (TTS)

ตอบมาเป็นรูปแบบ JSON เท่านั้น:
{{
  "text": "เนื้อหาบทความแบบเต็มสำหรับอ่านออกเสียง...",
  "tone": "serious",
  "voice": "niwat"
}}
"""
            response = model.generate_content(prompt, generation_config={"temperature": 0.4})
            
            cleaned = response.text.strip()
            cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
            cleaned = re.sub(r"```$", "", cleaned).strip()
            
            payload = json.loads(cleaned)
            payload["source"] = action.get("source")
            payload["chat_id"] = action.get("chat_id")
            
            with open(QUEUE_FILE, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
                
            print("Agent worker finished successfully.")
            
        elif action_type == "morning_brief":
            target_date = action.get("date")
            print(f"Morning Brief action started. Target date: {target_date}")
            
            title, pdf_url = fetch_morning_brief_pdf(target_date)
            print(f"Found PDF URL: {pdf_url}")
            
            pdf_response = requests.get(pdf_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
            pdf_bytes = pdf_response.content
            
            with io.BytesIO(pdf_bytes) as f:
                reader = PyPDF2.PdfReader(f)
                raw_text = ""
                for page in reader.pages:
                    raw_text += page.extract_text() + "\n"
                    
            cleaned_text = despace(raw_text)
            model = configure_model()
            
            prompt = f"""
คุณคือ Jarvis (Full-Text Reader) ผู้ช่วยของบอส
ภารกิจ: สกัดเนื้อหาภายใต้หัวข้อ "ประเด็นที่น่าติดตาม" หรือ "Interesting Issues" จากบทวิเคราะห์ Morning Brief ภาษาไทยด้านล่างนี้
กติกาที่ต้องปฏิบัติตามอย่างเคร่งครัด:
1. ให้ดึงข้อความภาษาไทยทั้งหมดที่อยู่ภายใต้หัวข้อ "ประเด็นที่น่าติดตาม" หรือ "Interesting Issues" (รวมหัวข้อย่อยและเนื้อหาทั้งหมดในส่วนนั้น)
2. **ห้ามย่อ ห้ามสรุป** ให้ดึงเนื้อหาออกมาคำต่อคำตรงตามตัวอักษรให้ครบถ้วนสมบูรณ์ที่สุด ห้ามตัดทอนประโยคเด็ดขาด
3. หากมีคำแปลกๆ หรือสะกดผิด หรือเว้นวรรคแปลกๆ ให้แก้ไขให้อ่านง่ายเป็นธรรมชาติสำหรับภาษาไทย
4. ห้ามมีคำนำหรือคำอธิบายประกอบใดๆ ให้ตอบเฉพาะ JSON ตามโครงสร้างด้านล่างนี้เท่านั้น

ตอบกลับในรูปแบบ JSON นี้เท่านั้น:
{{
  "text": "เนื้อหาทั้งหมดที่สกัดมาคำต่อคำจากส่วนประเด็นที่น่าติดตาม...",
  "tone": "serious",
  "voice": "niwat"
}}

เนื้อหาบทวิเคราะห์:
{cleaned_text}
"""
            response = model.generate_content(prompt, generation_config={"temperature": 0.2})
            
            cleaned = response.text.strip()
            cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
            cleaned = re.sub(r"```$", "", cleaned).strip()
            
            payload = json.loads(cleaned)
            
            # Generate the beautiful Glassmorphism Report Card
            try:
                card_text = str(payload.get("text") or "")
                card_text = card_text.replace("\n\n", "\n")
                card_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "morning_brief_card.png")
                render_report_card(
                    title="ประเด็นน่าติดตามเช้านี้",
                    content=card_text,
                    output_path=card_path,
                    badge="📢 MORNING BRIEF",
                    theme_color="violet"
                )
                payload["photo_path"] = card_path
            except Exception as card_err:
                print(f"Failed to generate morning brief card: {card_err}")
            
            payload["source"] = action.get("source")
            payload["chat_id"] = action.get("chat_id")
            
            with open(QUEUE_FILE, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
                
            print("Morning Brief extraction finished successfully.")
            
        elif action_type == "start_remote_approver":
            print("Starting Telegram Remote Approver...")
            bat_path = r"C:\Project\Telegram-Remote-Approver\start.bat"
            # ใช้ creationflags=subprocess.CREATE_NEW_CONSOLE เพื่อให้รันในหน้าต่างใหม่
            subprocess.Popen([bat_path], creationflags=subprocess.CREATE_NEW_CONSOLE)
            
            payload = {
                "text": "ระบบรีโมทมือถือเปิดทำงานเรียบร้อยแล้วครับบอส",
                "source": action.get("source"),
                "chat_id": action.get("chat_id"),
                "speech": {
                    "tone": "friendly",
                    "voice": "niwat",
                    "rate": "+0%",
                    "pitch": "+0Hz",
                    "provider": "auto",
                    "cache": False
                }
            }
            with open(QUEUE_FILE, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
            print("Started Telegram Remote Approver.")

        elif action_type == "run_agentic_task":
            prompt = action.get("prompt", "ไม่มีคำสั่ง")
            print(f"Starting Coding Agent with prompt: {prompt}")
            
            try:
                if genai is None:
                    raise RuntimeError("Missing google.generativeai")
                api_key = get_env_value("GEMINI_API_KEY", allow_legacy_config=True)
                genai.configure(api_key=api_key)
                
                agent_model = genai.GenerativeModel(
                    "gemini-flash-latest", 
                    tools=[read_file, write_file, run_cmd, search_web, fetch_content]
                )
                
                chat = agent_model.start_chat()
                sys_prompt = "You are a local coding assistant. You can read/write files and run terminal commands to help the user. Answer in Thai. Keep the final summary concise.\nUser Command: "
                response = chat.send_message(sys_prompt + prompt)
                
                # Manual tool calling loop with 2.5-second sleep to respect the 5 requests/min rate limit
                for _ in range(6):
                    calls = []
                    if response.candidates and response.candidates[0].content.parts:
                        for part in response.candidates[0].content.parts:
                            if part.function_call:
                                calls.append(part.function_call)
                                
                    if not calls:
                        break
                        
                    # Sleep to respect rate limits
                    time.sleep(2.5)
                    
                    tool_responses = []
                    for call in calls:
                        name = call.name
                        args = call.args
                        print(f"[Agent Tool] Calling tool {name} with args: {args}")
                        
                        result = None
                        try:
                            arg_dict = dict(args)
                            if name == "read_file":
                                result = read_file(**arg_dict)
                            elif name == "write_file":
                                result = write_file(**arg_dict)
                            elif name == "run_cmd":
                                result = run_cmd(**arg_dict)
                            elif name == "search_web":
                                result = search_web(**arg_dict)
                            elif name == "fetch_content":
                                result = fetch_content(**arg_dict)
                            else:
                                result = f"Error: Tool {name} not found."
                        except Exception as e:
                            result = f"Error executing tool: {e}"
                            
                        tool_responses.append(
                            genai.protos.Part(
                                function_response=genai.protos.FunctionResponse(
                                    name=name,
                                    response={"result": str(result)}
                                )
                            )
                        )
                        
                    time.sleep(2.5) # Sleep before submitting tool responses back to model
                    response = chat.send_message(tool_responses)
                
                final_text = response.text.strip()
                final_text = re.sub(r'\*+', '', final_text)
                final_text = re.sub(r'#+', '', final_text)
                
                payload = {
                    "text": final_text,
                    "source": action.get("source"),
                    "chat_id": action.get("chat_id"),
                    "speech": {
                        "tone": "serious",
                        "voice": "niwat",
                        "rate": "+0%",
                        "pitch": "+0Hz",
                        "provider": "auto",
                        "cache": False
                    }
                }
                
                # Generate beautiful search/research report card
                try:
                    card_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_report_card.png")
                    render_report_card(
                        title="ผลลัพธ์การสืบค้นและทำงาน",
                        content=final_text,
                        output_path=card_path,
                        badge="⚙️ JARVIS AGENT",
                        theme_color="cyan"
                    )
                    payload["photo_path"] = card_path
                except Exception as card_err:
                    print(f"Failed to generate agent report card: {card_err}")
                    
            except Exception as ex:
                print(f"Agentic task failed: {ex}")
                payload = {
                    "text": "ขออภัยครับบอส ระบบ Agent ย่อยทำงานผิดพลาดครับ",
                    "source": action.get("source"),
                    "chat_id": action.get("chat_id"),
                    "speech": {"tone": "calm", "voice": "niwat", "cache": False}
                }
                
            with open(QUEUE_FILE, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
            print("Agentic task finished.")

        else:
            print(f"Unknown action: {action_type}")
            
    except Exception as e:
        print(f"Agent worker error: {e}")
        error_payload = {
            "text": "ขออภัยครับบอส ระบบดึงข้อมูลจากเว็บมีปัญหาครับ",
            "source": action.get("source"),
            "chat_id": action.get("chat_id") if 'action' in locals() else None,
            "tone": "calm",
            "voice": "niwat"
        }
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(error_payload, f, ensure_ascii=False)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_agent(sys.argv[1])
