import os

# Search for any .md file in the project
md_files = []
for root, dirs, files in os.walk("C:\\Project\\Jarvis Assistant"):
    for file in files:
        if file.endswith(".md"):
            md_files.append(os.path.join(root, file))

print("Markdown files found in project:")
for f in md_files:
    print(f)
