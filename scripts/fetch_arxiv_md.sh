#!/usr/bin/env bash
# Fetch arxiv papers via arxiv2md.org REST API.
# Replaces broken ar5iv extractions with native-HTML Markdown.
#
# Args: arxiv IDs (with optional version, e.g. 2205.06908 or 2205.06908v2)

set -euo pipefail

OUT_DIR="raw/papers"
DATE="2026-08-12"
API="https://arxiv2md.org/api/markdown"

fetch_one() {
  local id="$1"
  local short="${id%%v*}"  # strip version for filename
  local slug="$2"

  echo "Fetching arXiv:${id} -> ${slug}"
  curl -fsSL "${API}?url=${id}&remove_refs=false&remove_toc=false&remove_citations=false&frontmatter=true" \
    -o "${OUT_DIR}/${DATE}-${slug}-arxiv${short}.md"
  local size=$(wc -c < "${OUT_DIR}/${DATE}-${slug}-arxiv${short}.md")
  echo "  ${size} bytes"
}

fetch_one "2205.06908"   "Neural-Fly"
fetch_one "2307.15852"   "Girard-2024-DimensionlessPolicies"
fetch_one "2003.04663"   "Kaushik-2020-FAMLE"
fetch_one "1012.0806"    "Chowdhary-2010-ConcurrentLearning-CDC"
