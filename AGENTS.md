# Voice Assistant Script - Agent Rules

## Voice Interaction Rules

You should ONLY use voice synthesis (TTS) in the following three scenarios. For all other responses, provide only text.

### 1. Opening the System
When the user says "เปิดระบบจาวิส" or "open jarvis", start the system by running:
`powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Project\Jarvis Assistant\jarvis.ps1"`

### 2. Shutting Down the System
When the user says "ปิดระบบจาวิส" or "shutdown", speak a farewell and shut down.
Command:
`powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$t=@'รับทราบครับบอส กำลังปิดระบบจาร์วิสครับ แล้วพบกันใหม่ครับ'@; & 'C:\Project\Jarvis Assistant\speak.ps1' -Text $t"`

### 3. Morning Brief (มอนิ่งบรีฟ)
When the user says "มอนิ่งบรีฟ", the assistant must navigate to https://www.sbito.co.th/Research.aspx, identify the Morning Brief article for the specific date mentioned (or the latest if no date is given), and extract ONLY the content under the "Interesting Issues" (ประเด็นที่น่าติดตาม) section. Read this entire section aloud to the user exactly as it is without summarizing.

## CRITICAL: Mandatory Tool Execution
- **NEVER** just paste a command in your response text without running it if it is meant to be executed.
- **ALWAYS** use the `run_command` tool to execute these commands.
- Verify execution by checking the logs for successful playback or script initialization.
