import json
from pathlib import Path

uncached = Path('.graphify_uncached.txt').read_text().splitlines()
CHUNK = 25
chunks = []
for i in range(0, len(uncached), CHUNK):
    chunks.append(uncached[i:i+CHUNK])

Path('.graphify_chunks.json').write_text(json.dumps(chunks))
print(f'Created {len(chunks)} chunks')
for i, c in enumerate(chunks):
    print(f'  chunk {i+1}: {len(c)} files')