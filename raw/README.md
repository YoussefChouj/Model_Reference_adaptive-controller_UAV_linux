# raw/ — Immutable Source Documents

This directory contains source material for the project wiki. Files here are **never
modified** — they are the ground truth that wiki pages are compiled from.

## Structure

```
raw/
└── papers/           # Papers converted via pdf-to-md pipeline
    ├── _archived/    # Stale files: pre-pipeline outputs, old naming, source PDFs
    │   ├── pre-pipeline/  # Converted files from before the pipeline existed
    │   ├── neurofly_*.md   # Early Neural-Fly conversions (various tools)
    │   └── *.pdf          # Source PDFs for reference
    ├── *-briefing.md  # Grabbed-paper notes (source: OpenClaw wiki_inbox)
    └── *-converted.md # Output of pdf-to-md.py (images/ and .jsonl paired)
```

## Naming convention

```
<YYYY-MM-DD>-<FirstAuthor>-<Year>-<ShortTitle>-converted.md
<YYYY-MM-DD>-<FirstAuthor>-<Year>-<ShortTitle>-converted-images/
<YYYY-MM-DD>-<FirstAuthor>-<Year>-<ShortTitle>-converted-raw.jsonl
```

The pipeline looks up existing briefings to get clean author/title names; otherwise falls
back to the arXiv ID or bare PDF filename.

## How to add a paper

1. Paper lands via `python scripts/pull_wiki_inbox.py` (auto at session start), or manually
   drop the PDF into this directory.
2. Convert: `python scripts/pdf-to-md.py path/to/paper.pdf`
3. Ingest into wiki — use the `grill-paper` skill or `/wiki` command.

## Archived files

`_archived/` is read-only. The two sub-folders:

| Folder | Contents |
|--------|----------|
| `pre-pipeline/` | All paper_reader output generated before `pdf-to-md.py` existed |
| root | Source PDFs, old NeuroFly conversions |

Do not edit archived files. If you need to re-convert a paper, delete its
`*-converted*` outputs and re-run `pdf-to-md.py`.
