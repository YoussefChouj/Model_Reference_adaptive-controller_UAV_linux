# External Research Tools (Apify MCP)

## What this is

Apify MCP gives this workspace live access to the web via thousands of pre-built scrapers (Actors) plus a general web browser. It is the escape hatch when the knowledge stack (`ccc`, wiki, docs) returns nothing, when you need real-time or post-training-cutoff data, or when you are in a loop that local code cannot resolve.

## When to reach for Apify

Use Apify when any of these is true:

| Situation | Signal phrase | Recommended Actor |
|-----------|--------------|-----------------|
| Agent is looping on the same failed assumption | "let me try another approach" twice without progress | `rag-web-browser` |
| Need real-time or post-2025-cutoff data | "current", "latest", "recent", "as of today" | `rag-web-browser` |
| Primary source needed, not AI summary | "what does the paper say", "what is the official docs" | `rag-web-browser` |
| YouTube tutorial or lecture | "video", "talk", "lecture", "explainer" | `starvibe/youtube-video-transcript` |
| Research a concept across multiple sources | "compare", "survey", "landscape", "what are the approaches to" | `rag-web-browser` |
| Documentation lookup | "how do I use X", "API docs", "official reference" | `search-apify-docs` |
| Structured data from a website | Social media, products, job listings, papers | `search-actors` + relevant Actor |
| Verify a fact that might have changed | "is this still the case", "has X been updated" | `rag-web-browser` |

**When NOT to use Apify:**
- The knowledge stack (`ccc search`, wiki, docs) already has the answer — check it first
- Deterministic firmware behavior — live firmware reads (`livewatch`) or code inspection
- Math, derivations, stability proofs — use `free-reason` skill instead

## Available Actors

### General web scraping
**`apify/rag-web-browser`** — web browser for RAG pipelines
- Queries Google Search and scrapes top N pages in clean Markdown
- Input: `query` (Google keywords or URL), `maxResults` (1–10), `outputFormats` (markdown/text)
- Cost: ~0.005 CU/run on free tier
- Best for: broad research, fact-checking, reading current docs

### YouTube
**`starvibe/youtube-video-transcript`** — transcript + metadata from a single video
- Input: `youtube_url`, `language` (ISO 639-1, e.g. "en"), `include_transcript_text` (boolean)
- Output: `transcript_text`, `transcript[]` (timestamped segments), `title`, `view_count`, `like_count`, `channel_name`, `published_at`, `description`
- Cost: $0.005/video (~4.5s runtime)
- Best for: extracting lecture/tutorial content for wiki ingestion or analysis

**`codepoetry/youtube-transcript-ai-scraper`** — transcript with Whisper AI fallback
- Falls back to Whisper transcription if no captions available
- Input: `startUrls` (array of URLs), `languages`, `enableAiFallback`, `outputFormats` (json/srt/vtt/text)
- Cost: $0.001/video (captions) + $0.012/min (AI transcription)
- Best for: auto-caption-only videos without manual subtitles

**`johnvc/YoutubeTranscripts`** — cheapest bulk option
- $0.00001/video, supports bulk URL lists
- Best for: batch transcript collection

### Documentation
**`search-apify-docs`** — full-text search Apify/Crawlee docs
- Input: `docSource` (apify/crawlee-js/crawlee-py), `query` (keywords)
- Best for: Apify API questions

**`fetch-apify-docs`** — fetch a specific docs page by URL
- Input: `url`
- Best for: reading a known docs page in full

### Finding the right Actor
**`search-actors`** — search Apify Store by keyword
- Input: `keywords` (1–3 terms, e.g. "arxiv", "twitter posts")
- Returns: Actor name, description, pricing, input fields, rating
- Best for: discovering whether an Actor exists for a platform before writing scraper code

## Workflow

```
1. search-actors (keywords: "platform topic")
   → find actor name + input schema

2. fetch-actor-details (actor: "username/name", output: { inputSchema: true })
   → confirm fields, get defaults

3. call-actor (actor: "username/name", input: { ... }, waitSecs: 30)
   → returns runId + datasetId

4. get-actor-run (runId, waitSecs: 10)
   → poll until SUCCEEDED/FAILED

5. get-dataset-items (datasetId, fields: "field1,field2,...")
   → retrieve results
```

For `rag-web-browser` (simplified — no dataset polling):
```
1. apify--rag-web-browser (query: "...", maxResults: 3, waitSecs: 30)
   → returns datasetId directly

2. get-dataset-items (datasetId, fields: "markdown,metadata.title")
   → retrieve content
```

## Cost and limits

| Actor | Cost | Notes |
|-------|------|-------|
| `rag-web-browser` | ~0.005 CU/run | 1 request = 1 page scraped |
| `starvibe/youtube-video-transcript` | $0.005/video | Fast, reliable |
| `search-actors` | free | Discovery only |
| `search-apify-docs` | free | Apify docs only |

Free tier compute units reset monthly. `rag-web-browser` at 0.005 CU/run gives ~200 scrapes/month.

## Setup and auth

**MCP config** — `.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "apify": {
      "url": "https://mcp.apify.com?tools=actors,docs,apify/rag-web-browser"
    }
  }
}
```

**Auth:** Apify MCP uses OAuth — Cursor triggers a browser redirect on first use after adding the entry. No API token needed. If tools don't appear after adding to `mcp.json`, reload the Cursor window (File → Reload Window).

**Tool names:** Apify tools appear with `__` double-underscore prefix in this session:
- `apify__mcp__search__actors`
- `apify__mcp__fetch__actor__details`
- `apify__mcp__call__actor`
- `apify__mcp__get__actor__run`
- `apify__mcp__get__dataset__items`
- `apify__mcp__apify____rag__web__browser`
- `apify__mcp__search__apify__docs`
- `apify__mcp__fetch__apify__docs`

## Common gotchas

- **`rag-web-browser` on YouTube:** hits YouTube's landing page, not video content. Use `starvibe/youtube-video-transcript` for video transcripts.
- **`rag-web-browser` on arXiv:** arXiv HTML pages are messy — use `codepoetry/youtube-transcript-ai-scraper` with Whisper disabled, or search for a PDF and use the PDF's URL directly.
- **Actor not found:** Apify free tier may not include all paid Actors. Check pricing before running.
- **Empty dataset:** Actor may have returned 0 items — check `run.status` and `storages.datasets.default.itemCount`.
- **OAuth expired:** If tools return auth errors after a period, reload the Cursor window to re-trigger OAuth.
- **MCP tool names:** Must use `apify__mcp__` prefix (double underscore) — single underscore or dot-notation does not work in this workspace.
- **Dataset expiry:** Apify datasets expire after ~7 days. Retrieve and persist important results promptly.

## Wiki inbox (separate external pipeline)

Papers and notes from the OpenClaw grab-bag server are synced automatically before each session:

```bash
python scripts/pull_wiki_inbox.py
```

Output goes to `raw/papers/`. If new papers arrive, the agent tells you — options are **ingest now** (wiki INGEST flow) or a **learning session** (`grill-paper` skill). See `.cursor/rules/wiki-inbox-autopull.mdc`.

## See also

- [Knowledge Gate Enforcement](concepts/knowledge-gate-enforcement.md) — always check the knowledge stack before reaching for external tools
- [Graphify Doc Extraction Pattern](concepts/graphify-doc-extraction-pattern.md) — pattern-based code extraction for non-Apify research
