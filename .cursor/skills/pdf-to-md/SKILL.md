---
name: pdf-to-md
description: >
  Convert a PDF paper to Markdown. Use when the user says "convert this paper",
  "run paper_reader", or "turn this PDF into markdown". Handles engine selection,
  setup, output organisation, and image handling.
---

# PDF → Markdown

## Engines

Three backends via `--engine`:

| Engine | Speed | Images | When to use |
|--------|-------|--------|-------------|
| `pdf-inspector` (default) | **~0.2 s** | No | Research papers, fast extraction, clean text |
| `paper-reader` | ~5 min | Yes (YOLO) | Need embedded figures, diagrams, tables |
| `both` | 0.2 s + 5 min | Graft from paper-reader | Best text quality + image references |

**pdf-inspector** (Firecrawl, open-source Rust) reads PDF content streams directly.
No OCR, no API key, pre-built wheels for Python 3.8+. Best for text-heavy research papers.

**paper-reader** (CiroZhang) uses DocLayNet YOLO for layout detection + figure extraction.
Heavier but extracts images. First run downloads ~521 MB of YOLO weights.

## Full pipeline

```
OpenClaw wiki_inbox/
        ↓  (session-start auto-pull or python scripts/pull_wiki_inbox.py)
raw/papers/  ← grabbed notes + PDFs land here
        ↓  python scripts/pdf-to-md.py
raw/papers/<YYYY-MM-DD>-<Author>-<Year>-<Title>.md       ← canonical output
raw/papers/<YYYY-MM-DD>-<Author>-<Year>-<Title>-images/ ← paper-reader images only
raw/papers/<YYYY-MM-DD>-<Author>-<Year>-<Title>-raw.jsonl ← paper-reader jsonl only
        ↓  (manual or grill-paper skill)
wiki/  ← ingested into the project wiki
```

## Prerequisites

### pdf-inspector (default, no setup needed)

```bash
# Already in requirements.txt — just install it
.venv/bin/pip install pdf-inspector
```

### paper-reader (optional, for images)

```bash
# Clone the tool
mkdir -p ~/tools && git clone --depth=1 https://github.com/CiroZhang/paper_reader.git ~/tools/paper_reader

# Create isolated venv (numpy 1.26.4 conflicts with project numpy 2.x)
cd ~/tools/paper_reader
python3.12 -m venv .venv

# Install deps + huggingface_hub (missing from upstream requirements.txt)
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
.venv/bin/pip install -q huggingface_hub

# Pre-fetch DocLayNet YOLOv8X weights (~521 MB)
# curl uses HTTPS_PROXY; huggingface_hub uses httpx which does NOT support socks://
mkdir -p ~/tools/paper_reader/yolo_model
curl -fsSL \
  -o ~/tools/paper_reader/yolo_model/doclaynet.pt \
  "https://huggingface.co/malaysia-ai/YOLOv8X-DocLayNet-Full-1024-42/resolve/main/weights/best.pt"
```

## Usage — one command

```bash
# Default: pdf-inspector only (fastest, ~0.2 s)
python scripts/pdf-to-md.py path/to/paper.pdf

# With images: run both, then graft paper-reader images into pdf-inspector markdown
python scripts/pdf-to-md.py path/to/paper.pdf --engine both

# Legacy: paper-reader only (slow, extracts images natively)
python scripts/pdf-to-md.py path/to/paper.pdf --engine paper-reader
```

The wrapper handles everything in one shot:

1. Runs the chosen engine(s) in a temp directory (no cross-contamination)
2. Copies output to `raw/papers/` under the correct name
3. Fixes image paths so they reference the local `*-images/` folder
4. Names output using the briefing filename convention

## Naming logic

```
<YYYY-MM-DD>-<FirstAuthor>-<Year>-<ShortTitle>
```

Priority (highest → lowest):

| Source | Example output |
|--------|---------------|
| Matching `*-briefing.md` in `raw/papers/` (same arXiv ID in frontmatter) | `2026-08-13-Girard-2024-DimensionlessPolicies-converted.md` |
| Bare arXiv ID in PDF filename | `2026-08-13-2205.06908.md` |
| Generic filename | `2026-08-13-my-paper.md` |

Briefing lookup: scans `raw/papers/*-briefing.md` for `arxiv: <ID>` or `arXiv: <ID>`
in the frontmatter `sources:` field. Use the briefing filename convention
(`YYYY-MM-DD-<Author>-<Year>-<Title>-briefing.md`) to get clean output names.

## Output files

| File | When created | Contents |
|------|-------------|----------|
| `*-converted.md` | Always | Canonical markdown (pdf-inspector or paper-reader) |
| `*-images/` | `--engine paper-reader` or `--engine both` | Extracted PNG figures from paper-reader |
| `*-raw.jsonl` | `--engine paper-reader` or `--engine both` | paper-reader raw per-page JSON |

pdf-inspector does NOT extract images. Use `--engine both` to get images from paper-reader
grafted into pdf-inspector text at figure-caption positions.

## Options

```bash
python scripts/pdf-to-md.py path/to/paper.pdf \
  --output-root raw/papers/           # default: raw/papers/
  --paper-reader-root ~/tools/paper_reader  # default: ~/tools/paper_reader
  --skip-copy                        # run engine but leave output in tmp (debug)
```

## Batch (multiple PDFs)

```bash
for pdf in paper1.pdf paper2.pdf paper3.pdf; do
  python scripts/pdf-to-md.py "$pdf"
done
```

paper_reader itself can handle multiple PDFs per run, but running one at a time via
the wrapper gives per-paper control and cleaner error messages.

## When to use which engine

**Use pdf-inspector (default) when:**
- The paper is text-based (journal articles, arXiv preprints, reports)
- Speed matters (0.2 s vs 5 min)
- You need clean text for wiki ingestion, summarisation, or citation extraction
- The paper has simple figures that you can re-create or skip

**Use `--engine both` when:**
- The paper has important figures, diagrams, or tables you need to reference
- You want pdf-inspector's clean text AND paper-reader's image files

**Use `--engine paper-reader` when:**
- The PDF is scanned/image-based (requires OCR)
- You need the raw JSONL per-page structure
- You want native image extraction without the extra pdf-inspector step

## Verify the PDF before converting

```bash
.venv/bin/python -c "
import fitz
d = fitz.open('path/to/paper.pdf')
print(d[0].get_text()[:300])
print(f'--- {len(d)} pages ---')
"
```

## Known issues

| Issue | Cause | Fix |
|-------|-------|-----|
| `ModuleNotFoundError: huggingface_hub` | Not in upstream requirements.txt | `.venv/bin/pip install huggingface_hub` |
| `ValueError: Unknown scheme for proxy URL socks://...` | `httpx` doesn't grok `socks://` | Pre-fetch weights with curl; `--no-auto-download` is set automatically |
| Very slow on 50+ page PDFs | CPU YOLO inference | Use `--engine pdf-inspector` instead (0.2 s); paper-reader ~5 min |
| Wrong paper extracted | Wrong arXiv ID | Verify with `fitz` first |
| `paper_reader venv not found` | Not at default path | Pass `--paper-reader-root` |
| Images not extracted | pdf-inspector doesn't extract images | Use `--engine both` or `--engine paper-reader` |
| Images not grafted in both mode | Grafting uses figure-caption matching | Check that `*-images/` contains figures from paper-reader |

## If you need LaTeX math output

Use docling or Mathpix API instead. pdf-inspector and paper_reader are right for:

- Fast, lightweight figure + text extraction
- Papers where PNG formulas are acceptable
- Reference wiki pages where the prose is the main value
