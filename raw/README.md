# raw/ — Immutable Source Documents

This directory contains source material for the project wiki. Files here are **never modified** — they are the ground truth that wiki pages are compiled from.

## Structure

```
raw/
├── papers/      # Academic papers, datasheets, reference docs
├── notes/       # Project notes, architectural decisions, interfaces
├── web/         # Web articles, blog posts, forum discussions
└── transcripts/ # Session transcripts, meeting notes
```

## Current Sources

| File | Description |
|------|-------------|
| notes/decisions.md | Architectural decisions (from docs/decisions.md) |
| notes/interfaces.md | Cross-subsystem interface contracts (from docs/interfaces.md) |
| notes/research-topics.md | Research domain overview |

## How to Add Sources

1. Drop files into the appropriate subdirectory
2. Run `/wiki` (for general knowledge) or `/project-wiki` (for code architecture)
3. The skill will ingest and compile wiki pages automatically
