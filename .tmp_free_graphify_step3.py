import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

uncached_path = Path('.graphify_uncached.json')
if not uncached_path.exists():
    print('Missing .graphify_uncached.json. Run Step 2 first.', file=sys.stderr)
    sys.exit(1)

uncached = json.loads(uncached_path.read_text(encoding='utf-8'))
if not uncached:
    Path('.graphify_free_extract.json').write_text(
        json.dumps({'nodes': [], 'edges': [], 'hyperedges': []}, indent=2),
        encoding='utf-8',
    )
    print('No uncached files. Wrote empty extraction file.')
    sys.exit(0)

run_agent = Path(os.path.expanduser('~')) / '.claude' / 'skills' / 'copilot-agent' / 'run_agent.py'
if not run_agent.exists():
    print(f'run_agent.py not found at {run_agent}. Install /copilot-agent skill first.', file=sys.stderr)
    sys.exit(1)

extract_path = Path('.graphify_free_extract.json')
if extract_path.exists():
    merged = json.loads(extract_path.read_text(encoding='utf-8'))
    merged.setdefault('nodes', [])
    merged.setdefault('edges', [])
    merged.setdefault('hyperedges', [])
else:
    merged = {'nodes': [], 'edges': [], 'hyperedges': []}

processed_files = {
    n.get('source_file')
    for n in merged.get('nodes', [])
    if isinstance(n, dict) and n.get('source_file')
}

agent_out = Path('.agent_out') / 'extractions'
agent_out.mkdir(parents=True, exist_ok=True)
cwd = str(Path('.').resolve())

for filepath in uncached:
    if filepath in processed_files:
        print(f'Skipping already extracted: {filepath}')
        continue

    if not Path(filepath).exists():
        print(f'Skipping missing file: {filepath}', file=sys.stderr)
        continue

    print(f'Processing: {filepath}')

    file_hash = hashlib.md5(filepath.encode()).hexdigest()[:8]
    safe_name = filepath.replace('/', '_').replace('\\', '_').replace(':', '')[:40]
    out_file = agent_out / f'{file_hash}_{safe_name}.json'

    prompt = (
        f'You are building a knowledge graph of this codebase. '
        f'Extract entities and relationships from: {filepath}\n\n'
        f'Use your file-reading tools to read the FULL file (no truncation). '
        f'Follow key imports or references to understand cross-file context.\n\n'
        f'Output ONLY valid JSON (no markdown fences) to: {out_file.resolve()}\n'
        f'Schema: {{"nodes":[{{"id":"snake_case_id","label":"Human Name",'
        f'"file_type":"code|document|config","source_file":"{filepath}"}}],'
        f'"edges":[{{"source":"id1","target":"id2",'
        f'"relation":"implements|references|calls|imports|extends|rationale_for",'
        f'"confidence":"EXTRACTED|INFERRED","confidence_score":0.85,'
        f'"source_file":"{filepath}"}}],"hyperedges":[]}}\n\n'
        f'Rules:\n'
        f'- EXTRACTED: explicitly stated in the file\n'
        f'- INFERRED: reasonably implied (score 0.6-0.9)\n'
        f'- All node ids in snake_case\n'
        f'- source_file must be exactly: {filepath}'
    )

    try:
        result = subprocess.run(
            ['python', str(run_agent), 'doc_extraction', prompt, '--cwd', cwd],
            capture_output=True, text=True, timeout=600,
        )
        if result.returncode != 0:
            print(f'Agent failed for {filepath}: {result.stderr[:300]}', file=sys.stderr)
            continue
    except Exception as exc:
        print(f'Agent error for {filepath}: {exc}', file=sys.stderr)
        continue

    if not out_file.exists():
        print(f'No output file produced for {filepath}, skipping.', file=sys.stderr)
        continue

    try:
        parsed = json.loads(out_file.read_text(encoding='utf-8'))
    except Exception as exc:
        print(f'JSON parse error for {filepath}: {exc}', file=sys.stderr)
        continue

    merged['nodes'].extend(parsed.get('nodes', []))
    merged['edges'].extend(parsed.get('edges', []))
    merged['hyperedges'].extend(parsed.get('hyperedges', []))
    processed_files.add(filepath)

    extract_path.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    print(f'Checkpoint saved after: {filepath}')

extract_path.write_text(
    json.dumps(merged, ensure_ascii=False, indent=2),
    encoding='utf-8',
)
print(f"Saved extraction bundle: {len(merged.get('nodes', []))} nodes, {len(merged.get('edges', []))} edges")
