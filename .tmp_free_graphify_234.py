import json
import os
import sys
from pathlib import Path
import requests

from graphify.cache import check_semantic_cache, save_semantic_cache
from graphify.detect import detect

result = detect(Path('.'))
all_files = []
for category in ['document', 'image']:
    all_files.extend(result.get('files', {}).get(category, []))

_, _, _, uncached = check_semantic_cache(all_files)
Path('.graphify_uncached.json').write_text(json.dumps(uncached, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'UNCACHED_COUNT_START={len(uncached)}')

extract_path = Path('.graphify_free_extract.json')
if extract_path.exists():
    merged = json.loads(extract_path.read_text(encoding='utf-8'))
    merged.setdefault('nodes', [])
    merged.setdefault('edges', [])
    merged.setdefault('hyperedges', [])
else:
    merged = {'nodes': [], 'edges': [], 'hyperedges': []}

if uncached:
    api_key = os.environ.get('OPENROUTER_API_KEY', '')
    if not api_key:
        print('OPENROUTER_API_KEY is not set.', file=sys.stderr)
        sys.exit(1)

    config = json.load(open(os.path.expanduser('~/.claude/openrouter_models.json'), encoding='utf-8'))
    models = config['tasks']['doc_extraction']['models']
    system_prompt = config['tasks']['doc_extraction']['system_prompt']
    proxy = os.environ.get('HTTPS_PROXY', '') or os.environ.get('https_proxy', '')
    proxies = {'https': proxy} if proxy else {}

    processed_files = {
        n.get('source_file')
        for n in merged.get('nodes', [])
        if isinstance(n, dict) and n.get('source_file')
    }

    for filepath in uncached:
        if filepath in processed_files:
            print(f'Skipping already extracted: {filepath}')
            continue

        path = Path(filepath)
        if not path.exists():
            print(f'Skipping missing file: {filepath}', file=sys.stderr)
            continue

        print(f'Processing: {filepath}')
        content = path.read_text(encoding='utf-8', errors='replace')
        extraction_prompt = f'''Extract entities and relationships from this file.

File: {filepath}

Rules:
- EXTRACTED: relationship explicit in source
- INFERRED: reasonable inference (confidence 0.6-0.9)
- AMBIGUOUS: uncertain (confidence 0.1-0.3)
- For rationale sections (WHY decisions were made), create rationale_for edges

Output ONLY valid JSON (no markdown fences):
{{"nodes":[{{"id":"snake_case_id","label":"Human Name","file_type":"document","source_file":"{filepath}"}}],"edges":[{{"source":"id1","target":"id2","relation":"references|implements|rationale_for","confidence":"EXTRACTED|INFERRED","confidence_score":0.8,"source_file":"{filepath}"}}],"hyperedges":[]}}

Content:
{content[:8000]}'''

        parsed = None
        for model in models:
            try:
                response = requests.post(
                    'https://openrouter.ai/api/v1/chat/completions',
                    headers={
                        'Authorization': f'Bearer {api_key}',
                        'Content-Type': 'application/json',
                    },
                    json={
                        'model': model,
                        'messages': [
                            {'role': 'system', 'content': system_prompt},
                            {'role': 'user', 'content': extraction_prompt},
                        ],
                        'max_tokens': 4000,
                    },
                    proxies=proxies,
                    timeout=45,
                )
                if response.status_code == 200:
                    text = response.json()['choices'][0]['message']['content']
                    text = text.replace('```json', '').replace('```', '').strip()
                    parsed = json.loads(text)
                    print(f'Extracted {filepath} with {model}')
                    break
                elif response.status_code == 429:
                    print(f'Rate limited on {model} for {filepath}, trying next...', file=sys.stderr)
                else:
                    print(f'{model} returned {response.status_code} for {filepath}, trying next...', file=sys.stderr)
            except Exception as exc:
                print(f'{model} failed on {filepath}: {exc}', file=sys.stderr)

        if not parsed:
            print(f'All models failed for {filepath}, skipping.', file=sys.stderr)
            continue

        merged['nodes'].extend(parsed.get('nodes', []))
        merged['edges'].extend(parsed.get('edges', []))
        merged['hyperedges'].extend(parsed.get('hyperedges', []))
        extract_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'Checkpoint saved after: {filepath}')

# Merge and cache

graph_path = Path('graphify-out/graph.json')
graph = json.loads(graph_path.read_text(encoding='utf-8')) if graph_path.exists() else {'directed': False, 'multigraph': False, 'graph': {}, 'nodes': [], 'links': [], 'hyperedges': []}
graph.setdefault('nodes', [])
graph.setdefault('links', [])
graph.setdefault('hyperedges', [])

existing_node_ids = {n.get('id') for n in graph['nodes'] if isinstance(n, dict) and n.get('id')}
for node in merged.get('nodes', []):
    if not isinstance(node, dict):
        continue
    node_id = node.get('id')
    if node_id and node_id not in existing_node_ids:
        graph['nodes'].append(node)
        existing_node_ids.add(node_id)

existing_link_keys = {
    (e.get('source'), e.get('target'), e.get('relation'), e.get('source_file'))
    for e in graph['links'] if isinstance(e, dict)
}
added_links = 0
for edge in merged.get('edges', []):
    if not isinstance(edge, dict):
        continue
    source = edge.get('source')
    target = edge.get('target', edge.get('to'))
    relation = edge.get('relation')
    source_file = edge.get('source_file')
    if not source or not target:
        continue
    key = (source, target, relation, source_file)
    if key in existing_link_keys:
        continue
    normalized = dict(edge)
    normalized['source'] = source
    normalized['target'] = target
    normalized['_src'] = source
    normalized['_tgt'] = target
    normalized.setdefault('weight', 1.0)
    normalized.pop('to', None)
    graph['links'].append(normalized)
    existing_link_keys.add(key)
    added_links += 1

graph['hyperedges'].extend(merged.get('hyperedges', []))
graph.pop('edges', None)
graph_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding='utf-8')
save_semantic_cache(merged.get('nodes', []), merged.get('edges', []), merged.get('hyperedges', []))
print(f"MERGED_NODES={len(merged.get('nodes', []))} MERGED_LINKS_ADDED={added_links}")

# Regenerate report
try:
    from graphify.report import generate_report
    generate_report(graph, Path('graphify-out'))
except Exception:
    from networkx.readwrite import json_graph
    from graphify.analyze import god_nodes, surprising_connections, suggest_questions
    from graphify.cluster import cluster, score_all
    from graphify.report import generate
    G = json_graph.node_link_graph(graph, edges='links')
    communities = cluster(G)
    cohesion = score_all(G, communities)
    gods = god_nodes(G)
    surprises = surprising_connections(G, communities)
    labels = {cid: f'Community {cid}' for cid in communities}
    questions = suggest_questions(G, communities, labels)
    detection = detect(Path('.'))
    report = generate(G, communities, cohesion, labels, gods, surprises, detection, {'input':0,'output':0}, str(Path('.')), suggested_questions=questions)
    Path('graphify-out/GRAPH_REPORT.md').write_text(report, encoding='utf-8')
print('GRAPH_REPORT.md regenerated')
