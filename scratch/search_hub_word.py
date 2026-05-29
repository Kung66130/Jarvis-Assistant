import os

# Search for the word 'hub' in all files in the workspace
found_occurrences = []
for root, dirs, files in os.walk("C:\\Project\\Jarvis Assistant"):
    for file in files:
        if file.endswith(('.py', '.md', '.txt', '.ps1', '.bat', '.json')):
            filepath = os.path.join(root, file)
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, 1):
                        if 'hub' in line.lower():
                            found_occurrences.append((file, line_num, line.strip()))
            except Exception:
                pass

print(f"Found {len(found_occurrences)} occurrences of 'hub':")
for file, line_num, text in found_occurrences[:20]:
    print(f"File: {file} (Line {line_num}): {text}")
