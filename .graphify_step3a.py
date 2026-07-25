import sys, json
from graphify.extract import collect_files, extract
from pathlib import Path

detect = json.loads(Path('.graphify_detect.json').read_text())
code_files = []
for f in detect.get('files', {}).get('code', []):
    p = Path(f)
    if p.is_dir():
        code_files.extend(collect_files(p))
    else:
        code_files.append(p)

# dedupe
seen = set()
unique = []
for p in code_files:
    s = str(p.resolve())
    if s not in seen:
        seen.add(s)
        unique.append(p)

print(f'AST input: {len(unique)} code files', file=sys.stderr)

# Process serially in chunks to avoid worker-pool failures
all_nodes = []
all_edges = []
chunk = 50
for i in range(0, len(unique), chunk):
    files = unique[i:i+chunk]
    try:
        r = extract(files)
        all_nodes.extend(r.get('nodes', []))
        all_edges.extend(r.get('edges', []))
    except Exception as e:
        print(f'chunk {i}-{i+chunk} failed: {e}', file=sys.stderr)

result = {'nodes': all_nodes, 'edges': all_edges, 'input_tokens': 0, 'output_tokens': 0}
Path('.graphify_ast.json').write_text(json.dumps(result, indent=2))
print(f'AST: {len(all_nodes)} nodes, {len(all_edges)} edges')