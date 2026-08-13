---
name: pdf-to-md
description: >
  Convert one or more PDF papers to Markdown using CiroZhang/paper_reader.
  Use when the user says "convert this paper", "run paper_reader", or "turn this PDF into markdown".
  Handles setup, correct invocation, and output organisation.
---

# PDF → Markdown with paper_reader

## Full pipeline

```
OpenClaw wiki_inbox/
        ↓  (session-start auto-pull or python scripts/pull_wiki_inbox.py)
raw/papers/  ← grabbed notes + PDFs land here
        ↓  python scripts/pdf-to-md.py
raw/papers/<YYYY-MM-DD>-<Author>-<Year>-<Title>-converted.md
raw/papers/<YYYY-MM-DD>-<Author>-<Year>-<Title>-converted-images/
raw/papers/<YYYY-MM-DD>-<Author>-<Year>-<Title>-converted-raw.jsonl
        ↓  (manual or grill-paper skill)
wiki/  ← ingested into the project wiki
```

The `pull_wiki_inbox.py` step runs automatically at session start. After conversion,
the next step is a wiki-ingestion learning session — use the `grill-paper` skill or
run `/wiki` if a `wiki-ingest` command exists.

## Prerequisites (one-time setup)

```bash
# Clone the tool
mkdir -p ~/tools && git clone --depth=1 https://github.com/CiroZhang/paper_reader.git ~/tools/paper_reader

# Create isolated venv (numpy 1.26.4 in requirements.txt conflicts with project numpy 2.x)
cd ~/tools/paper_reader
python3.12 -m venv .venv

# Install deps + huggingface_hub (missing from upstream requirements.txt)
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
.venv/bin/pip install -q huggingface_hub

# Pre-fetch DocLayNet YOLOv8X weights (~521 MB on disk)
# curl goes via HTTPS_PROXY (http://) which works; huggingface_hub uses httpx
# which does NOT support socks:// — so curl is the reliable path
mkdir -p ~/tools/paper_reader/yolo_model
curl -fsSL \
  -o ~/tools/paper_reader/yolo_model/doclaynet.pt \
  "https://huggingface.co/malaysia-ai/YOLOv8X-DocLayNet-Full-1024-42/resolve/main/weights/best.pt"
```

## Usage — one command

```bash
python scripts/pdf-to-md.py path/to/paper.pdf
```

The wrapper handles everything in one shot:

1. Runs paper_reader in a temp directory (clean — no cross-contamination between runs)
2. Copies output to `raw/papers/` under the correct name
3. Fixes image paths so they reference the local `*-converted-images/` folder
4. Names output using the briefing filename convention (see below)

## Naming logic

The output filename encodes the paper identity:

```
<YYYY-MM-DD>-<FirstAuthor>-<Year>-<ShortTitle>
```

Priority (highest → lowest):

| Source | Example output |
|---|---|
| Matching `*-briefing.md` in `raw/papers/` (same arXiv ID in frontmatter) | `2026-08-13-Girard-2024-DimensionlessPolicies-converted.md` |
| Bare arXiv ID in PDF filename | `2026-08-13-2205.06908-converted.md` |
| Generic filename | `2026-08-13-my-paper-converted.md` |

Briefing lookup: scans `raw/papers/*-briefing.md` for `arxiv: <ID>` or `arXiv: <ID>`
in the frontmatter `sources:` field. Use the briefing filename convention
(`YYYY-MM-DD-<Author>-<Year>-<Title>-briefing.md`) to get clean output names.

## Batch (multiple PDFs)

```bash
for pdf in paper1.pdf paper2.pdf paper3.pdf; do
  python scripts/pdf-to-md.py "$pdf"
done
```

paper_reader itself can handle multiple PDFs per run, but running one at a time via
the wrapper gives per-paper control and cleaner error messages.

## Options

```bash
python scripts/pdf-to-md.py path/to/paper.pdf \
  --output-root raw/papers/          # default: raw/papers/
  --paper-reader-root ~/tools/paper_reader  # default: ~/tools/paper_reader
  --skip-copy                        # run paper_reader but leave output in tmp (debug)
```

## Verify the PDF before converting

paper_reader is tuned for arXiv layout. Wrong text = wrong arXiv ID:

```bash
~/tools/paper_reader/.venv/bin/python -c "
import fitz
d = fitz.open('path/to/paper.pdf')
print(d[0].get_text()[:300])
print(f'--- {len(d)} pages ---')
"
```

## Archived pre-pipeline outputs

Old manual paper_reader outputs (pre-pipeline) are in `raw/papers/_archived/`.
Do not edit them — they are read-only snapshots of the old workflow.

## Known issues

| Issue | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: huggingface_hub` | Not in upstream requirements.txt | `.venv/bin/pip install huggingface_hub` |
| `ValueError: Unknown scheme for proxy URL socks://...` | `httpx` doesn't grok `socks://` | Pre-fetch weights with curl; `--no-auto-download` is set automatically |
| Very slow on 50+ page PDFs | CPU YOLO inference | Expected; a 41-page paper ~5 min on this box |
| Wrong paper extracted | Wrong arXiv ID | Verify with `fitz` first |
| `paper_reader venv not found` | Not at default path | Pass `--paper-reader-root` |

## If you need LaTeX math output

Use docling or Mathpix API instead. paper_reader is right for:

- Fast, lightweight figure + text extraction (CPU, ~3–6 min per paper)
- Papers where PNG formulas are acceptable
- Reference wiki pages where the prose is the main value
