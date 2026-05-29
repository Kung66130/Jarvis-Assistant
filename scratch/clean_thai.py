import re

def despace(text):
    # Join characters that are separated by single spaces but look like Thai words
    # This is a simple heuristic: if a line has many single spaces between characters, join them.
    def replacer(match):
        return match.group(0).replace(" ", "")
    
    # Matches sequences of (Thai char + space)
    thai_char_pattern = r'[\u0E00-\u0E7F]\s(?=[\u0E00-\u0E7F])'
    text = re.sub(thai_char_pattern, lambda m: m.group(0)[0], text)
    return text

with open("morning_brief_full.txt", "r", encoding="utf-8") as f:
    content = f.read()

cleaned = despace(content)

with open("morning_brief_cleaned.txt", "w", encoding="utf-8") as f:
    f.write(cleaned)

print("Cleaned text saved to morning_brief_cleaned.txt")
