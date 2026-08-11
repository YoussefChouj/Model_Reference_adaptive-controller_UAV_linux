# External Research Tools (Apify MCP)

> **Status: verified 2026-08-12.** Earlier versions of this page documented the
> Smithery-proxied MCP and `apify__mcp__*` tool names — both stale. The current
> setup uses Apify's direct MCP, and tools appear with short hyphenated names.
> See `.agent_memory/lessons.jsonl` `fix-mcp-apify-2026-08-12` for the full
> correction and the auth-incident summary.

## What this is

Apify MCP gives this workspace live access to the web via thousands of pre-built
scrapers (Actors) plus a general web browser. It is the escape hatch when the
knowledge stack (`ccc`, wiki, docs) returns nothing, when you need real-time or
post-training-cutoff data, or when you are in a loop that local code cannot
resolve.

## When to reach for Apify

Use Apify when any of these is true:

| Situation | Signal phrase | Recommended Actor |
|-----------|---------------|-------------------|
| Agent is looping on the same failed assumption | "let me try another approach" twice without progress | `apify--rag-web-browser` |
| Need real-time or post-2025-cutoff data | "current", "latest", "recent", "as of today" | `apify--rag-web-browser` |
| Primary source needed, not an AI summary | "what does the paper say", "what is the official docs" | `apify--rag-web-browser` |
| YouTube tutorial or lecture | "video", "talk", "lecture", "explainer" | `starvibe/youtube-video-transcript` |
| Research a concept across multiple sources | "compare", "survey", "landscape", "what are the approaches to" | `apify--rag-web-browser` |
| Documentation lookup | "how do I use X", "API docs", "official reference" | `search-apify-docs` |
| Structured data from a website | Social media, products, job listings, papers | `search-actors` + relevant Actor |
| Verify a fact that might have changed | "is this still the case", "has X been updated" | `apify--rag-web-browser` |

**When NOT to use Apify:**

- The knowledge stack (`ccc search`, wiki, docs) already has the answer — check it first
- Deterministic firmware behavior — live firmware reads (`livewatch`) or code inspection
- Math, derivations, stability proofs — use `free-reason` skill instead

## Available Actors (verified 2026-08-12)

### General web scraping

**`apify/rag-web-browser`** — web browser for RAG pipelines

- Queries Google Search and scrapes top N pages in clean Markdown
- Input: `query` (Google keywords or URL), `maxResults` (1–10), `outputFormats` (markdown/text/html)
- Cost: ~0.005 CU/run on free tier
- Best for: broad research, fact-checking, reading current docs
- Tool name on this workspace: `apify--rag-web-browser` (single dedicated tool)

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

## Tool names (this is what you'll actually call)

| Tool name | Purpose |
|-----------|---------|
| `search-actors` | Find Actors by keyword |
| `fetch-actor-details` | Get input schema, README, pricing for a specific Actor |
| `call-actor` | Run any Actor (after reading its schema) |
| `get-actor-run` | Poll a run's status, get datasetId/keyValueStoreId |
| `get-dataset-items` | Read scraped results |
| `get-key-value-store-record` | Read a single key-value record |
| `apify--rag-web-browser` | Dedicated tool: scrape a URL or Google query |
| `search-apify-docs` | Search Apify/Crawlee docs |
| `fetch-apify-docs` | Fetch a specific docs page |
| `abort-actor-run` | Stop a running Actor |
| `mcp_auth` | Trigger OAuth flow (if connection is `needsAuth`) |

There are also `*-widget` variants (`call-actor-widget`, `get-actor-run-widget`,
`search-actors-widget`, `fetch-actor-details-widget`) that render an interactive
UI element instead of returning data. Use them only when the user explicitly
asks to see live progress visually; for normal programmatic use prefer the
silent (non-widget) variants.

Naming rule: **short hyphenated names, no `apify__mcp__` prefix**. The one
exception is `apify--rag-web-browser` — the double-hyphen encodes the actor
path `apify/rag-web-browser` (slash → double-hyphen).

## Setup and auth

### The right config (current, 2026-08-12)

`.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "apify": {
      "url": "https://mcp.apify.com?tools=actors,docs,apify/rag-web-browser"
    }
  }
}
```

No `Authorization` header. Cursor's MCP runtime handles OAuth transparently.

### Why this and not the Smithery proxy

There is an alternative path that **does not work reliably** in this workspace:

```json
// DO NOT USE — Smithery gateway drops sub-connection auth every ~24 hours
{
  "toolbox": {
    "url": "https://mcp.smithery.ai/<your-handle>",
    "headers": { "Authorization": "Bearer …" }
  }
}
```

The Smithery bearer token is persistent and works for the parent connection.
But each downstream sub-connection (`apify-mcp`, `slack`, `linear`, …) needs
its own OAuth grant stored on Smithery's server side. That grant is what kept
disappearing — every ~24 hours, the prompt returned and the connection was
`auth_required`. We confirmed this twice (2026-08-11 worked, 2026-08-12 broken).

**Use the direct Apify MCP.** Cursor stores the OAuth token in `state.vscdb`
encrypted, same as other Cursor-managed MCPs. Persists across sessions.

### Triggering OAuth for the first time

When the entry is added to `mcp.json` and the connection is `needsAuth`:

1. Call `mcp_auth` on the `user-apify` server (or use any tool — Cursor prompts the browser flow on first call).
2. Browser opens to `https://console.apify.com` — log in and grant the requested scopes.
3. Cursor caches the token. From then on, all calls succeed without prompts.

**No Cursor window reload needed.** The dialog appears only when the auth
record file (`~/.config/Cursor/User/globalStorage/mcp-oauth-attempts/
<attempt-id>.json`) is created and the matching token is not yet in
`state.vscdb`.

### Diagnostic probing

If a tool call fails, check why before assuming a config bug:

| Tool | What it tells you |
|------|-------------------|
| `get_toolbox_status` (on `user-toolbox`) | Per-server state: `ready` / `needsAuth` / `auth_required` / `error`. Returns `setupUrl` when auth is required. |
| `GetMcpTools({ server: "user-apify" })` | Verifies the server is loaded and lists tool names. Returns `serverStatus: "needsAuth"` if Cursor hasn't completed OAuth yet. |
| `curl -X POST https://mcp.apify.com …` | Manual HTTP probe; bypasses Cursor's runtime. Useful for confirming whether the Apify server itself is reachable. |

## Workflow

### For a structured web scrape (most common)

```
1. search-actors(keywords: "platform topic")
   → find actor name + input fields

2. fetch-actor-details(actor: "username/name", output: { inputSchema: true })
   → confirm required vs optional fields, get defaults

3. call-actor(actor: "username/name", input: { ... }, waitSecs: 30)
   → returns runId + datasetId when complete

4. get-actor-run(runId, waitSecs: 10)
   → poll until SUCCEEDED / FAILED (only if call-actor was non-terminal)

5. get-dataset-items(datasetId, fields: "field1,field2,...", limit: 100)
   → retrieve results
```

### For a quick web read (simpler)

```
1. apify--rag-web-browser(query: "...", maxResults: 3, waitSecs: 30)
   → returns datasetId directly

2. get-dataset-items(datasetId, fields: "markdown,metadata.title")
   → retrieve content
```

### For YouTube

```
1. call-actor(actor: "starvibe/youtube-video-transcript",
              input: { youtube_url: "...", language: "en" },
              waitSecs: 30)
   → returns datasetId

2. get-dataset-items(datasetId, fields: "transcript_text,title,channel_name")
   → read transcript
```

## Cost and limits

| Actor | Cost | Notes |
|-------|------|-------|
| `apify/rag-web-browser` | ~0.005 CU/run | 1 request = 1 page scraped |
| `starvibe/youtube-video-transcript` | $0.005/video | Fast, reliable |
| `search-actors` | free | Discovery only |
| `search-apify-docs` | free | Apify docs only |

Free tier compute units reset monthly. `apify/rag-web-browser` at 0.005 CU/run
gives ~200 scrapes/month on the free tier.

**Datasets expire after ~7 days.** Retrieve and persist important results
promptly (write to `wiki/literature/`, `docs/`, or `raw/`).

## Common gotchas

- **`apify--rag-web-browser` on YouTube:** hits YouTube's landing page, not video content. Use `starvibe/youtube-video-transcript` for video transcripts.
- **`apify--rag-web-browser` on arXiv:** arXiv HTML pages are messy — prefer a PDF URL (Google-search returns the PDF link) or use `codepoetry/youtube-transcript-ai-scraper` with Whisper disabled.
- **Actor not found:** Apify free tier may not include all paid Actors. Check pricing in `fetch-actor-details` before running.
- **Empty dataset:** Actor may have returned 0 items — check `run.status` and `storages.datasets.default.itemCount` in `get-actor-run`.
- **`fetch-actor-details` is your first stop** before `call-actor`. The Actor's `input` schema may have required fields you don't expect.
- **`waitSecs` cap is 45.** For long Actors, start with `waitSecs: 0` (fire-and-forget) and poll with `get-actor-run`.
- **Tool-call naming:** short hyphenated names (e.g. `search-actors`), not `apify__mcp__search__actors`. The double-underscore form is wrong; see the lesson.
- **Datasets expire after ~7 days.** Retrieve and persist important results promptly.
- **Auth debug:** if you see `Authorization required` responses pointing at `connect.smithery.ai/...`, you're hitting the wrong (Smithery-proxied) path. Check `.cursor/mcp.json` for the direct `apify` entry.

## Wiki inbox (separate external pipeline)

Papers and notes from the OpenClaw grab-bag server are synced automatically
before each session:

```bash
python scripts/pull_wiki_inbox.py
```

Output goes to `raw/papers/`. If new papers arrive, the agent tells you —
options are **ingest now** (wiki INGEST flow) or a **learning session**
(`grill-paper` skill). See `.cursor/rules/wiki-inbox-autopull.mdc`.

## See also

- [Knowledge Gate Enforcement](concepts/knowledge-gate-enforcement.md) — always check the knowledge stack before reaching for external tools
- [Graphify Doc Extraction Pattern](concepts/graphify-doc-extraction-pattern.md) — pattern-based code extraction for non-Apify research
- `.agent_memory/lessons.jsonl` — `fix-mcp-apify-2026-08-12` entry with the auth-incident summary
