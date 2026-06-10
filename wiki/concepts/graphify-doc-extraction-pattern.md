# Graphify Doc Extraction — Pattern-Based Extractor

**Region**: Workflow & Recipes
**Tags**: graphify, tooling, extraction, wiki-indexing

## Problem

Running graphify's wiki extraction via `copilot-agent` with `effort: high` + `autopilot: true` produces JSON parse errors for every document:

```
JSON error wiki\MRAC Theory.md: Expecting value: line 1 column 2 (char 1)
```

## Root Cause Chain

1. `effort: high` + `autopilot: true` puts copilot-agent into full codebase exploration mode
2. The agent explores files, hits permission errors, then writes a markdown *summary* — not JSON
3. The output file starts with `[copilot-agent] task=doc_extraction status=...` (a status log line)
4. `json.loads("[copilot-agent]...")` → `[` at pos 0 starts an array, `c` at pos 1 is not valid → error

The fallback code in the script wrote all of stdout to the extraction file without validating it was valid JSON.

## Fix

Replace the LLM-agent approach with a local Python pattern-based extractor. No API, no quota, guaranteed valid JSON.

**Location**: `.tmp_graphify_extract.py` (or `graphify/extract_docs.py` if moved permanently)

### Extraction patterns

| Pattern | Produces | Confidence |
|---------|----------|------------|
| `^#{1,3} header` | child node + `references` edge | 1.0 |
| `` `path.c` `` / `` `path.h` `` | `references` edge to file node | 0.9 |
| `` `FunctionName(...)` `` | `references` edge to symbol node | 0.75 |
| `[[wiki link]]` | `references` edge to page node | 0.85 |

### Core functions

```python
def _slug(s):
    return re.sub(r'[^a-z0-9]+', '_', s.lower()).strip('_')

def extract_markdown(filepath, abs_path):
    content = abs_path.read_text(encoding='utf-8', errors='replace')
    nodes, edges = [], []
    file_id = _slug(filepath.replace('\\', '/').replace('/', '_').replace('.', '_'))
    # ... regex loops for headers, code refs, function calls, wiki links
    return {'nodes': nodes, 'edges': edges, 'hyperedges': []}
```

## Gotchas

- `copilot-agent` with any `effort` level is unsuitable for narrow extraction tasks — it explores broadly
- The JSON error `Expecting value: line 1 column 2` specifically means position 0 is `[` and position 1 is not a valid JSON value; this is the signature of the agent status log prefix
- After extraction, `generate_report()` requires `networkx` — call with `py -3.13` not bare `python`
- `detect()` in the report pipeline requires a `Path` object, not a string

## Running the extractor

```powershell
py -3.13 .tmp_graphify_extract.py
```

Then regenerate the report manually if needed:

```powershell
py -3.13 -c "
from graphify.report import generate_report
from networkx.readwrite import json_graph
import json
from pathlib import Path
ROOT = Path('.')
graph = json.loads((ROOT / 'graphify-out/graph.json').read_text())
generate_report(graph, ROOT / 'graphify-out')
"
```

## Result (2026-05-25)

- Before: 1,606 nodes, 1,708 edges (18 wiki files failed)
- After: 3,396 nodes, 4,836 edges (+819 new links from wiki)
