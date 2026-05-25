import hashlib, json, os, subprocess, sys
from pathlib import Path

root = Path(r'C:\Users\Acer\Desktop\UAV_lab\FreeRTOS---Six_Degrees_of_Freedom _Adaptive_controller')
uncached_path = root / '.graphify_uncached.json'
if not uncached_path.exists():
    print('Missing .graphify_uncached.json', file=sys.stderr); sys.exit(1)

uncached = json.loads(uncached_path.read_text(encoding='utf-8'))
if not uncached:
    print('No uncached files.'); sys.exit(0)

run_agent = Path(os.path.expanduser('~')) / '.claude' / 'skills' / 'copilot-agent' / 'run_agent.py'
if not run_agent.exists():
    print(f'run_agent.py not found: {run_agent}', file=sys.stderr); sys.exit(1)

extract_path = root / '.graphify_free_extract.json'
if extract_path.exists():
    merged = json.loads(extract_path.read_text(encoding='utf-8'))
    merged.setdefault('nodes', []); merged.setdefault('edges', []); merged.setdefault('hyperedges', [])
else:
    merged = {'nodes': [], 'edges': [], 'hyperedges': []}

processed = {n.get('source_file') for n in merged.get('nodes', []) if isinstance(n, dict) and n.get('source_file')}
agent_out = root / '.agent_out' / 'extractions'
agent_out.mkdir(parents=True, exist_ok=True)
cwd = str(root)

for filepath in uncached:
    if filepath in processed:
        print(f'Skip (cached): {filepath}'); continue
    abs_path = root / filepath
    if not abs_path.exists():
        print(f'Skip (missing): {filepath}', file=sys.stderr); continue

    print(f'Extracting: {filepath}', flush=True)
    fh = hashlib.md5(filepath.encode()).hexdigest()[:8]
    safe = filepath.replace('/', '_').replace('\\', '_').replace(':', '')[:50]
    out_file = agent_out / f'{fh}_{safe}.json'

    prompt = (
        f'You are building a knowledge graph for a UAV firmware + ground-station project.\n'
        f'Extract entities and relationships from: {filepath}\n\n'
        f'Read the COMPLETE file at {abs_path} using your file-reading tools.\n'
        f'Follow key imports or cross-references to understand context.\n\n'
        f'Output ONLY valid JSON (no markdown fences) with this schema:\n'
        f'{{"nodes":[{{"id":"snake_case","label":"Human Name",'
        f'"file_type":"code|document|config","source_file":"{filepath}"}}],'
        f'"edges":[{{"source":"id1","target":"id2",'
        f'"relation":"implements|references|calls|imports|extends|rationale_for",'
        f'"confidence":"EXTRACTED|INFERRED","confidence_score":0.85,'
        f'"source_file":"{filepath}"}}],"hyperedges":[]}}\n'
        f'Write output to: {out_file.resolve()}\n'
        f'Rules: all node ids snake_case; source_file = exactly "{filepath}"'
    )

    try:
        r = subprocess.run(
            ['python', str(run_agent), 'doc_extraction', prompt, '--cwd', cwd],
            capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            print(f'Agent FAIL {filepath}: {r.stderr[:200]}', file=sys.stderr); continue
    except Exception as e:
        print(f'Agent ERROR {filepath}: {e}', file=sys.stderr); continue

    if not out_file.exists() and r.stdout.strip():
        out_file.write_text(r.stdout, encoding='utf-8')
    if not out_file.exists():
        print(f'No output for {filepath}', file=sys.stderr); continue

    try:
        parsed = json.loads(out_file.read_text(encoding='utf-8'))
    except Exception as e:
        print(f'JSON error {filepath}: {e}', file=sys.stderr); continue

    merged['nodes'].extend(parsed.get('nodes', []))
    merged['edges'].extend(parsed.get('edges', []))
    merged['hyperedges'].extend(parsed.get('hyperedges', []))
    processed.add(filepath)
    extract_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Checkpoint saved: {filepath}', flush=True)

# Step 4: merge into graph.json
from graphify.cache import save_semantic_cache
graph_path = root / 'graphify-out' / 'graph.json'
graph = json.loads(graph_path.read_text(encoding='utf-8')) if graph_path.exists() else \
    {'directed': False, 'multigraph': False, 'graph': {}, 'nodes': [], 'links': [], 'hyperedges': []}
graph.setdefault('nodes', []); graph.setdefault('links', []); graph.setdefault('hyperedges', [])

existing_ids = {n.get('id') for n in graph['nodes'] if isinstance(n, dict)}
for node in merged.get('nodes', []):
    if isinstance(node, dict) and node.get('id') not in existing_ids:
        graph['nodes'].append(node); existing_ids.add(node.get('id'))

existing_links = {(e.get('source'), e.get('target'), e.get('relation'), e.get('source_file'))
                  for e in graph['links'] if isinstance(e, dict)}
added = 0
for edge in merged.get('edges', []):
    if not isinstance(edge, dict): continue
    s, t, rel, sf = edge.get('source'), edge.get('target', edge.get('to')), edge.get('relation'), edge.get('source_file')
    if not s or not t: continue
    key = (s, t, rel, sf)
    if key in existing_links: continue
    n = dict(edge); n['source'] = s; n['target'] = t; n['_src'] = s; n['_tgt'] = t; n.setdefault('weight', 1.0)
    n.pop('to', None)
    graph['links'].append(n); existing_links.add(key); added += 1

graph['hyperedges'].extend(merged.get('hyperedges', []))
graph.pop('edges', None)
graph_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding='utf-8')
save_semantic_cache(merged.get('nodes', []), merged.get('edges', []), merged.get('hyperedges', []))
print(f'Merged: {len(merged.get("nodes", []))} nodes, {added} new links')

# Step 5: regenerate GRAPH_REPORT.md
import sys
try:
    from graphify.report import generate_report
    generate_report(graph, root / 'graphify-out')
except Exception:
    from networkx.readwrite import json_graph
    from graphify.analyze import god_nodes, surprising_connections, suggest_questions
    from graphify.cluster import cluster, score_all
    from graphify.detect import detect
    from graphify.report import generate
    G = json_graph.node_link_graph(graph, edges='links')
    communities = cluster(G); cohesion = score_all(G, communities)
    gods = god_nodes(G); surprises = surprising_connections(G, communities)
    labels = {cid: f'Community {cid}' for cid in communities}
    questions = suggest_questions(G, communities, labels)
    detection = detect(root)
    report = generate(G, communities, cohesion, labels, gods, surprises, detection,
                      {'input': 0, 'output': 0}, str(root), suggested_questions=questions)
    (root / 'graphify-out' / 'GRAPH_REPORT.md').write_text(report, encoding='utf-8')
print('GRAPH_REPORT.md regenerated')
print('DONE')
