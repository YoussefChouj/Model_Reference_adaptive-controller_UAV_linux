# PDF → Markdown Tools

Survey of tools for converting academic PDFs (with math, figures, tables) to Markdown.

## paper_reader (CiroZhang)

**Repo:** `https://github.com/CiroZhang/paper_reader`
**Stars:** 2 | **Forks:** 0 | **Status:** unmaintained

### What it does
- Trims margins + removes line numbers from arxiv PDFs
- Runs DocLayNet YOLOv8X (via `ultralytics`) to detect: text, captions, figures, tables, formulas
- Post-processes: license text, references stripped; section headers raised
- Outputs: `outputs/<paper>.md` + `outputs/images/` (PNG crops) + optional `raw_outputs/*.jsonl`

### What it does NOT do
- **No OCR** — formula regions are PNG crops, not LaTeX or accessible text
- **No accessible figures** — figures are image crops, not searchable text
- **No math rendering** — formula images embedded as `![Formula - ...](...)`

### Install gotchas
1. `requirements.txt` is missing `huggingface_hub` — Python API auto-download crashes
   → `pip install huggingface_hub` after requirements
2. `huggingface-cli` not on PATH in a clean venv — CLI download path silently fails
   → Python API (huggingface_hub) is the path that actually works
3. `httpx` used by huggingface_hub does not support `socks://` proxy scheme — only `socks5://`
   → unset `ALL_PROXY`/`all_proxy` for the download run, or pre-fetch with curl
4. DocLayNet weights are **521 MB on disk** (not the ~130 MB README implies)
   → Pre-fetch: `curl -fsSL -o yolo_model/doclaynet.pt https://huggingface.co/malaysia-ai/YOLOv8X-DocLayNet-Full-1024-42/resolve/main/weights/best.pt`

### Performance (Neural-Fly, 41 pages, CPU only)
- Trim + YOLO: 5m08s
- Output: 99 KB .md + 53 images (11 figures + 3 tables + 39 formula crops) + jsonl + removed sections
- Total disk: 3.6 MB

### Canonical invocation (with pre-fetched weights)
```bash
cd ~/tools/paper_reader
.venv/bin/python main.py /path/to/pdfs /path/to/output \
  --save-raw-json --save-removed --no-auto-download
```

### Is it the right tool?
Only if: you want arxiv PDF → markdown with figure/table crops, no math searchability needed.
If you need: math as LaTeX, accessible figures, higher accuracy → see alternatives below.

## Alternatives

| Tool | Math | OCR | License | Weight | Notes |
|------|------|-----|---------|--------|-------|
| MinerU (magic-pdf) | LaTeX | yes | Apache 2 | ~6 GB (torch + weights) | Best quality; needs GPU or patience |
| marker | LaTeX | yes | Apache 2 | ~3 GB (GPU) / ~2 GB (CPU) | Faster than MinerU |
| nougat | LaTeX | no | CC-BY-NC | ~2 GB | Meta's model; good math |
| docling | LaTeX | yes | MIT | ~200 MB | Light, CPU-friendly |
| olmocr | LaTeX | yes | Apache 2 | ~1 GB | allenai; good general |
| Mathpix | LaTeX | yes | SaaS | API call | 50 pages/mo free; best quality |
| **paper_reader** | PNG only | no | research | ~500 MB (CPU) | Only arxiv PDFs; heuristic layout |

For this project's papers (MRAC, SysID, EKF — math-heavy): **docling** or **Mathpix** are the practical choices.
For figure + text extraction without math: **paper_reader** is lightweight and fast.
