from graphify.cache import check_semantic_cache
from graphify.detect import detect
from pathlib import Path
import json

root = Path('.')

ignore_prefixes = []
ignore_file = root / '.graphifyignore'
if ignore_file.exists():
    for line in ignore_file.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            ignore_prefixes.append(line.replace('\\', '/'))

def is_ignored(filepath: str) -> bool:
    normalized = filepath.replace('\\', '/')
    return any(normalized.startswith(p) or ('/' + p) in ('/' + normalized) for p in ignore_prefixes)

result = detect(root)
all_files = []
for category in ['document', 'image']:
    all_files.extend(result.get('files', {}).get(category, []))

if ignore_prefixes:
    before = len(all_files)
    all_files = [f for f in all_files if not is_ignored(f)]
    print(f'Ignored {before - len(all_files)} files via .graphifyignore')

_, _, _, uncached = check_semantic_cache(all_files)
Path('.graphify_uncached.json').write_text(
    json.dumps(uncached, ensure_ascii=False, indent=2),
    encoding='utf-8'
)

if uncached:
    print(f'{len(uncached)} files need semantic extraction:')
    for f in uncached:
        print(f'  {f}')
else:
    print('All docs are cached. No extraction needed.')
