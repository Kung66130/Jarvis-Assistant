# Voice Assistant Script - Agent Rules

## Text-to-speech after every answer

After you produce your final answer to the user, speak the same text by running a PowerShell command.

Command:

`powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$t=@'<PASTE_SPOKEN_SUMMARY_ONLY_HERE>'@; & 'C:\Project\Jarvis Assistant\speak.ps1' -Provider sapi -Tone calm -Text $t"`

Notes:
- Paste the full final answer inside the here-string exactly as sent.
- For speech, DO NOT read commands, file paths, or code blocks. Speak only a short Thai summary (1-3 sentences).
- Keep the on-screen answer unchanged; only shorten what is spoken.
- Do not run other commands unless explicitly requested.

## Open Jarvis command

If the user says `เปิดระบบจาวิส` or `open jarvis`, start the interactive Jarvis loop by running:

`powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Project\Jarvis Assistant\jarvis.ps1"`
