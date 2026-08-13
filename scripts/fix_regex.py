#!/usr/bin/env python3
with open('scripts/pdf-to-md.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix in graft_images_into_markdown: figure number extraction
content = content.replace(
    'fig_match = re.search(r"(?:Figure|Table)\\\\s*(\\\\d+[A-Za-z]?)", image_line)',
    'fig_match = re.search(r"(?:Figure|Table)\\\\s*([A-Za-z0-9]+)", image_line)'
)

# Fix in _build_image_refs_from_jsonl: caption label extraction
content = content.replace(
    'm = re.search(r"(Figure \\\\d+[A-Za-z]?|Table \\\\d+[A-Za-z]?):", text)',
    'm = re.search(r"(Figure [A-Za-z0-9]+|Table [A-Za-z0-9]+)[:.]", text)'
)

with open('scripts/pdf-to-md.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done')
