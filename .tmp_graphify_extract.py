"""
Graphify semantic extraction — local pattern-based extractor for doc files.
No LLM needed: parses markdown headers, code refs, function mentions.
Guaranteed valid JSON, fast, no API quota used.
"""
import hashlib, json, re, sys
from pathlib import Path

ROOT         = Path(r'C:\Users\Acer\Desktop\UAV_lab\FreeRTOS---Six_Degrees_of_Freedom _Adaptive_controller')
uncached_path = ROOT / '.graphify_uncached.json'
extract_path  = ROOT / '.graphify_free_extract.json'

uncached = json.loads(uncached_path.read_text(encoding='utf-8')) if uncached_path.exists() else []
if not uncached:
    print('No uncached list — nothing to do.'); sys.exit(0)

if extract_path.exists():
    merged = json.loads(extract_path.read_text(encoding='utf-8'))
    merged.setdefault('nodes', []); merged.setdefault('edges', []); merged.setdefault('hyperedges', [])
else:
    merged = {'nodes': [], 'edges': [], 'hyperedges': []}

processed = {n.get('source_file') for n in merged['nodes'] if isinstance(n, dict) and n.get('source_file')}


def _slug(s):
    return re.sub(r'[^a-z0-9]+', '_', s.lower()).strip('_')


def extract_markdown(filepath, abs_path):
    """Pattern-based extraction from a markdown document."""
    content = abs_path.read_text(encoding='utf-8', errors='replace')
    nodes, edges = [], []

    file_id = _slug(filepath.replace('\\', '/').replace('/', '_').replace('.', '_'))
    nodes.append({'id': file_id, 'label': abs_path.stem,
                  'file_type': 'document', 'source_file': filepath})

    # Headers → child nodes
    for m in re.finditer(r'^#{1,3}\s+(.+)', content, re.MULTILINE):
        header = m.group(1).strip().rstrip('#').strip()
        if not header:
            continue
        hid = f'{file_id}__{_slug(header)}'[:80]
        nodes.append({'id': hid, 'label': header, 'file_type': 'document', 'source_file': filepath})
        edges.append({'source': file_id, 'target': hid, 'relation': 'references',
                      'confidence': 'EXTRACTED', 'confidence_score': 1.0, 'source_file': filepath})

    # Backtick code paths (.c / .h / .py files)
    for m in re.finditer(r'`([A-Za-z_][A-Za-z0-9_/\\.]+\.(?:c|h|py|md))`', content):
        ref = m.group(1).replace('\\', '/').replace('/', '_').replace('.', '_')
        ref_id = _slug(ref)
        edges.append({'source': file_id, 'target': ref_id, 'relation': 'references',
                      'confidence': 'EXTRACTED', 'confidence_score': 0.9, 'source_file': filepath})

    # Function calls like `mrac_update(...)` or `StabilizerTask`
    for m in re.finditer(r'`([A-Za-z_][A-Za-z0-9_]{3,})\s*(?:\([^)]{0,40}\))?`', content):
        sym = m.group(1)
        if sym.upper() == sym and '_' not in sym:
            continue  # skip ALL_CAPS constants
        edges.append({'source': file_id, 'target': _slug(sym), 'relation': 'references',
                      'confidence': 'INFERRED', 'confidence_score': 0.75, 'source_file': filepath})

    # Wiki cross-links [[page name]]
    for m in re.finditer(r'\[\[([^\]]+)\]\]', content):
        target_id = _slug(m.group(1))
        edges.append({'source': file_id, 'target': target_id, 'relation': 'references',
                      'confidence': 'EXTRACTED', 'confidence_score': 0.85, 'source_file': filepath})

    return {'nodes': nodes, 'edges': edges, 'hyperedges': []}


def extract_text(filepath, abs_path):
    """Minimal extraction for plain-text files: just a single node."""
    file_id = _slug(filepath.replace('\\', '/').replace('/', '_').replace('.', '_'))
    return {
        'nodes': [{'id': file_id, 'label': abs_path.name,
                   'file_type': 'document', 'source_file': filepath}],
        'edges': [], 'hyperedges': []
    }


DOC_EXTS = {'.md', '.txt', '.rst'}

for filepath in uncached:
    if filepath in processed:
        print(f'Skip (cached): {filepath}')
        continue

    abs_path = ROOT / filepath
    if not abs_path.exists():
        print(f'Skip (missing): {filepath}', file=sys.stderr)
        continue

    ext = abs_path.suffix.lower()
    if ext not in DOC_EXTS:
        print(f'Skip (not doc): {filepath}')
        continue

    print(f'Extracting: {filepath}', flush=True)
    try:
        if ext == '.md':
            parsed = extract_markdown(filepath, abs_path)
        else:
            parsed = extract_text(filepath, abs_path)
    except Exception as e:
        print(f'  ERROR {filepath}: {e}', file=sys.stderr)
        continue

    merged['nodes'].extend(parsed.get('nodes', []))
    merged['edges'].extend(parsed.get('edges', []))
    merged['hyperedges'].extend(parsed.get('hyperedges', []))
    processed.add(filepath)
    extract_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'  Done ({len(parsed["nodes"])} nodes, {len(parsed["edges"])} edges)', flush=True)

print(f'\nExtraction done: {len(merged["nodes"])} nodes, {len(merged["edges"])} edges')

# ── Merge into graph.json ──────────────────────────────────────────────────────
print('Merging into graph.json ...')
graph_path = ROOT / 'graphify-out' / 'graph.json'
graph = (
    json.loads(graph_path.read_text(encoding='utf-8')) if graph_path.exists()
    else {'directed': False, 'multigraph': False, 'graph': {}, 'nodes': [], 'links': [], 'hyperedges': []}
)
graph.setdefault('nodes', []); graph.setdefault('links', []); graph.setdefault('hyperedges', [])

existing_ids = {n.get('id') for n in graph['nodes'] if isinstance(n, dict)}
for node in merged['nodes']:
    if isinstance(node, dict) and node.get('id') not in existing_ids:
        graph['nodes'].append(node)
        existing_ids.add(node.get('id'))

existing_links = {
    (e.get('source'), e.get('target'), e.get('relation'), e.get('source_file'))
    for e in graph['links'] if isinstance(e, dict)
}
added = 0
for edge in merged['edges']:
    if not isinstance(edge, dict): continue
    s, t, rel, sf = edge.get('source'), edge.get('target', edge.get('to')), edge.get('relation'), edge.get('source_file')
    if not s or not t: continue
    key = (s, t, rel, sf)
    if key in existing_links: continue
    n = {**edge, 'source': s, 'target': t, '_src': s, '_tgt': t}
    n.setdefault('weight', 1.0); n.pop('to', None)
    graph['links'].append(n)
    existing_links.add(key)
    added += 1

graph['hyperedges'].extend(merged.get('hyperedges', []))
graph.pop('edges', None)
graph_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'graph.json updated: +{added} new links')

# ── Save semantic cache (skip dirs / bad paths) ────────────────────────────────
try:
    from graphify.cache import save_semantic_cache
    safe_nodes = [n for n in merged['nodes']
                  if isinstance(n, dict) and n.get('source_file') and (ROOT / n['source_file']).is_file()]
    safe_edges = [e for e in merged['edges']
                  if isinstance(e, dict) and e.get('source_file') and (ROOT / e['source_file']).is_file()]
    save_semantic_cache(safe_nodes, safe_edges, merged.get('hyperedges', []))
    print(f'Semantic cache saved ({len(safe_nodes)} nodes filtered to actual files)')
except Exception as e:
    print(f'Semantic cache save skipped: {e}', file=sys.stderr)

# ── Regenerate GRAPH_REPORT.md ─────────────────────────────────────────────────
print('Regenerating GRAPH_REPORT.md ...')
try:
    from graphify.report import generate_report
    generate_report(graph, ROOT / 'graphify-out')
except Exception:
    try:
        from networkx.readwrite import json_graph
        from graphify.analyze import god_nodes, surprising_connections, suggest_questions
        from graphify.cluster import cluster, score_all
        from graphify.detect import detect
        from graphify.report import generate
        G           = json_graph.node_link_graph(graph, edges='links')
        communities = cluster(G)
        cohesion    = score_all(G, communities)
        gods        = god_nodes(G)
        surprises   = surprising_connections(G, communities)
        labels      = {cid: f'Community {cid}' for cid in communities}
        questions   = suggest_questions(G, communities, labels)
        detection   = detect(ROOT)
        report      = generate(G, communities, cohesion, labels, gods, surprises,
                               detection, {'input': 0, 'output': 0}, str(ROOT),
                               suggested_questions=questions)
        (ROOT / 'graphify-out' / 'GRAPH_REPORT.md').write_text(report, encoding='utf-8')
    except Exception as e2:
        print(f'GRAPH_REPORT.md regeneration failed: {e2}', file=sys.stderr)

print('DONE')
