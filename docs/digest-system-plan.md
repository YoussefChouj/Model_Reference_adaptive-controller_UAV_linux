# Plan — Evolving the OpenClaw Literature Digest into an Academic Learning Digest System

**Status:** ✅ PLAN COMPLETE (grill session 2026-07-04) — ready for executor  
**Executor:** a separate agent will implement from this doc. All server work happens on  
`root@204.168.167.145` in `/home/openclaw/workspace/` (run as user `openclaw`,  
venv `/home/openclaw/openclaw_app/.venv/bin/python3`, secrets in `/home/openclaw/.openclaw/digest.env`,  
priorities in `/home/openclaw/notes/Literature/drone-mrac.md`).

## Current system (baseline, working)

*   `digest.py` (579 L): parses priority docs → fetches arXiv/OpenAlex(+IEEE gated off) → keyword score →  
    optional LLM rerank → caps → posts per-topic to Discord channels; state = flat last-500 id list.
*   `llm_layer.py` (197 L): map(3 free workers w/ paid twins)→reduce(deepseek-v4-pro reviewer);  
    returns None on failure → keyword fallback. **No per-channel cap on the LLM path.**
*   `extra_sources.py` (260 L): RSS (ArduPilot/PX4/IEEE-Spectrum/Hackaday), HN Algolia, Crossref  
    posted-content. Own copies of `_get`/SSL/UA/RECENT\_DAYS (duplicated from digest.py).
*   `grab_poller.py` (120 L): `!grab`/📥 → PDF fetch; WATCH list duplicates channel IDs.
*   Cron: digest 08:00 UTC daily. Proven live 2026-07-04: 15 papers incl. 3 → #inspiration.

## Architecture review findings (2026-07-04)

1.  **Fetcher seam half-formed** — 6 adapters, duplicated HTTP infra, hand-patched `collect()`. ⭐ enabling refactor.
2.  **Selection has no single owner** — caps in `apply_caps` (keyword path only), LLM path uncapped  
    per channel, `ensure_inspiration_floor` is a post-hoc patch.
3.  **State can't support feedback** — flat id list; blocks 👍/👎 learning loop, roll-ups, similarity checks.
4.  **Channel IDs triplicated** — digest.CHANNELS, grab\_poller.WATCH, priorities-doc route column.
5.  Minor: dead `interleave()`; `format_paper` lacks 2000-char guard; `openai/gpt-oss-120b` worker slot  
    fails JSON (swap it); cron failures silent (add crash-post to #briefing).

## Decisions (grill session)

### D1 — Registry first, as a strangler ✅

Build `sources.py`: registry `SOURCES = [(name, fetch_fn, env_toggle)]` with shared `http_get`;  
`collect()` iterates the registry. Existing fetchers wrapped untouched; old path kept as fallback  
for one week of green cron runs before deleting. Every new source afterward = one drop-in adapter file.

### D2 — Follow-the-professors: OpenAlex author-following is priority 1 ✅

*   Phase 1: user supplies professor/leader names → one-time OpenAlex author-ID resolution →  
    daily "new works by these author IDs" fetcher (free, fits paper-dict schema, routes by topic match).
*   Phase 2 (after P1 verified): X via **Twikit** (free scraping lib using user's own account).  
    **Guardrails (mandatory):** secondary/burner X account, cookie-based auth persisted on server,  
    1–2 searches/day with jittered timing, built as best-effort/disposable (X breaks scrapers; ToS/ban risk  
    accepted by user). No paid X API. Google/social search later via same adapter seam.
*   **Why Twikit and not web-search-with-site-filters (verified 2026-07-04):** since X's 2023 login
    walls, Google/DDG index only a sparse sliver of X (`site:x.com` returns a handful of results vs
    pages for old twitter.com). Web search cannot substitute for reading the timeline; Twikit
    (logged-in scrape) is the only free path to actual tweet content. Web-search adapters still cover
    the open web (lab pages, blogs) — and OpenAlex author-following catches the papers professors
    announce anyway.

### D3 — Chinese/Russian sources + China industry/language feed ✅

*   **ChinaXiv** (CAS preprints, open API) + **CyberLeninka** (Russian OA, API) adapters.  
    Papers route to normal topic channels with 🇨🇳/🇷🇺 tag.
*   **User is HSK5 and WANTS Chinese-language posts** (intl student in China, possible future career there):
    goal is technical vocabulary + industry landscape (companies, products, standards, research problems,
    hiring requirements) for robotics/drones. **Post format (amended 2026-07-04): Chinese original +
    English translation, plus pinyin + short gloss for words above ~HSK5** (one Qwen free-worker call
    per Chinese item does all three at post time).
*   **Chinese industry intel:** add free Chinese tech-media RSS to feeds (机器之心 jiqizhixin,
    36氪 robotics/hardware, 雷锋网) BEFORE paying for search APIs.
*   **Scope widened (amended 2026-07-04): China drone INDUSTRY feed, not just research.** New topic
    row(s) in the priorities doc with Chinese terms covering business / supply chains / low-altitude
    economy (无人机, 低空经济, 供应链, 大疆, eVTOL, 出海, 适航/标准, 招聘 …) so company news,
    supply-chain moves, standards, and hiring signals are fetched, scored, and routed like any topic.
    **Route: dedicated channel `#china-drone-robotics-industry`, ID `1522959199611650159`**
    (category 📁 RESEARCH CORE, ID `1479105850726551704`) — user created it 2026-07-04. Add to
    digest CHANNELS + grab_poller WATCH + priorities-doc route column.
*   **AI web search — one seam, two adapters, both accept Chinese queries:**
    *   **Tavily** (primary): free 1,000 credits/mo (enough at ~10 queries/day); language-agnostic —
        send Chinese terms directly. Chinese-web coverage thinner than a native engine but real.
        Bocha 博查 is NOT free — defer; revisit only if Chinese coverage feels thin.
    *   **`ddgs` (duckduckgo_search)** (secondary): free, keyless, decent Chinese coverage via
        Bing-family indexes, BUT rate-limits/blocks aggressively at volume (verified 2026-07-04).
        Best-effort adapter: few queries/day, jittered, degrades to [] like every fetcher. Never the
        sole source.

### D4 — YouTube / podcasts / courses — weekly learning digest ✅ (full build)

*   **Cadence & route:** weekly (Saturday 08:00 UTC cron, separate from daily paper digest) →
    existing unused channel **`#coursework`, ID `1479106309365432320`**. Add to grab_poller WATCH.
*   **Sources:**
    1.  **YouTube channel-following** — free, keyless: per-channel RSS
        (`https://www.youtube.com/feeds/videos.xml?channel_id=<ID>`) rows in the RSS fetcher.
        User to supply the follow list (control/robotics educators, CN robotics channels) — OPEN ITEM.
    2.  **YouTube keyword discovery** — YouTube Data API v3 search on priority terms (incl. Chinese
        terms). Quota 10,000 units/day, 100/search; weekly usage trivial. **User has created the key;
        it is deliberately NOT recorded in this doc — store as `YOUTUBE_API_KEY` in
        `/home/openclaw/.openclaw/digest.env` (chmod 600). Recommend restricting the key to YouTube
        Data API v3 in Google Cloud console.**
    3.  **Podcasts** — natively RSS; user supplies feed URLs — OPEN ITEM.
    4.  **Courses** — no good API; occasional Tavily/ddgs web-search queries ("course/公开课" + terms).
*   Items reuse the paper-dict schema (id `yt:<videoId>` etc.), same scoring/LLM rerank, same
    decision-log (D5) so 👍/👎 on videos feeds the taste memo too. Chinese videos get the D3
    translation+pinyin treatment.

### D5 — Memory + continuous learning loop ✅ (full design approved)

Today NOTHING is remembered: worker scores, reviewer verdicts, and every rejected candidate are
discarded when the run ends; state is a flat last-500 posted-id list (finding #3). Proposed design,
modeled on what production recommender/LLM-curation systems do (log implicit feedback → distill a
profile → feed it back into ranking), sized for a free-model budget — no fine-tuning:

1.  **Decision log** (`~/workspace/digest_log/YYYY-MM-DD.jsonl`, one line per candidate per run):
    id, title, source, channel, keyword score, worker mean+spread, reviewer verdict (posted/cut) and
    note, final relevance tier. Cheap (a few KB/day), rotates by month. This alone answers
    "what was filtered and why" for any past run.
2.  **Reaction joiner**: reuse grab_poller's `openclaw message read` machinery to read 👍/👎/📥 on
    digest posts and join them back to decision-log rows → labeled examples (liked / disliked /
    grabbed = strongest signal).
3.  **Weekly taste memo** (the continuous-learning part, runs on the 24/7 OpenClaw box): a weekly
    cron job feeds the last N weeks of labeled examples + reviewer notes to a free worker, which
    distills a compact "editor's memo" (~30 lines: what the user consistently grabs, ignores,
    downvotes; topics drifting up/down). The memo is injected into BOTH worker and reviewer prompts
    on subsequent runs. This is how the grading "gets smarter over time" without any training.
4.  Raw search results: keep the full fetched pool in the daily JSONL too (title/url/scores only,
    not abstracts) so future re-ranking experiments can be replayed offline.

### D6 — Sequencing + robustness batch ✅ (foundation-first, approved)

| Phase | Content | Gate before next phase |
|---|---|---|
| 0 | Robustness batch: swap `openai/gpt-oss-120b` worker slot (fails JSON — pick another free model that returns clean JSON); 2000-char guard in `format_paper` (split or truncate); on any uncaught exception in `main()`, post a short crash report to #briefing; delete dead `interleave()`; new `channels.py` = single source of truth for channel name→ID, imported by digest.py AND grab_poller.py | tests green + 1 green live cron run |
| 1 | D1 registry (`sources.py` strangler, shared `http_get`) **+ selection owner**: one `select(pool, caps, priorities)` that owns MAX_TOTAL/MAX_PER_CHANNEL/MAX_PER_TOPIC/inspiration-floor for BOTH keyword and LLM paths (fixes finding #2 — LLM path currently uncapped per channel) | tests green + 1 week green cron on registry path, then delete old collect() path |
| 2 | D5 data collection: decision log JSONL + reaction joiner (labels start accumulating now) | log file appears daily; joiner picks up a test 👍 |
| 3 | D2 P1: OpenAlex author-following adapter | standalone fetch of known-author works + green cron |
| 4 | D3: ChinaXiv + CyberLeninka adapters; CN media RSS rows; web-search seam (Tavily primary, ddgs best-effort); china-industry topic rows; translation+pinyin post-processor | each adapter standalone-tested; one CN item posted correctly formatted to `#china-drone-robotics-industry` |
| 5 | D4: weekly learning digest → `#coursework` (YT channel RSS, YT Data API search, podcast RSS, course web-search) | one manual weekly run posts correctly |
| 6 | Learners: D5 weekly taste memo (needs ≥3–4 weeks of labels from Phase 2); D2 P2 Twikit (needs burner account) | memo generated + visibly injected into prompts; Twikit fetch survives 1 week |

## Executor mandate

*   **Work method: `/tdd` skill, per phase.** Write failing tests first against each module's
    interface (fetch adapters: schema + degrade-to-[] on network failure via mocked `http_get`;
    `select()`: cap/floor invariants; post-processor: format contract), then implement to green.
    Tests live in `~/workspace/tests/`, runnable with the venv python via
    `python3 -m unittest discover tests` (stdlib only — no pytest dependency unless already installed).
*   The planner (Claude, this doc's author) audits each phase: contract adherence, test quality,
    no scope creep. Do not merge phases; do not start phase N+1 before phase N's gate is met.
*   Style: match existing codebase (stdlib-only urllib, print-logging with bracketed prefixes,
    graceful degradation everywhere). Every fetcher MUST return `[]` on any failure — the digest
    never dies because one source did.
*   Secrets: env vars in `/home/openclaw/.openclaw/digest.env` (chmod 600), NEVER in code, logs,
    the priorities doc, or this plan. Verify presence by length, never print values.
*   Discord posting is outward-facing: during development, test-post only to #briefing or use a
    dry-run flag; no unsolicited posts to topic channels until the phase gate run.

### Registry design sketch (Phase 1)

```python
# sources.py
SOURCES = [
    # (name, fetch_fn, env_toggle)  — fetch_fn(terms, n) -> [paper_dict], [] on failure
    ("arxiv",     digest.fetch_arxiv,        None),            # always on
    ("openalex",  digest.fetch_openalex,     None),
    ("ieee",      digest.fetch_ieee,         "IEEE_ENABLED"),
    ("rss",       extra_sources.fetch_rss,   "DIGEST_RSS"),
    ("hn",        extra_sources.fetch_hn,    "DIGEST_HN"),
    ("crossref",  extra_sources.fetch_crossref, "DIGEST_CROSSREF"),
    # later phases append: openalex_authors, chinaxiv, cyberleninka, tavily, ddgs, youtube, twikit
]

def collect(terms, n):
    pools = []
    for name, fn, toggle in SOURCES:
        if toggle and not _on(toggle):
            continue
        try:
            pools.append(fn(terms, n))
        except Exception as e:
            print(f"    [src] {name} FAILED: {e}"); pools.append([])
    return roundrobin(*pools)
```

Shared `http_get(url, headers=None, timeout=20, tries=2)` moves here; digest.py and
extra_sources.py import it (their local copies deleted at end of Phase 1).

**Adapter template** (each new source = one file/function):
`fetch_<name>(terms, n=8) -> [{id, title, abstract, url, authors, date, source}]`,
id prefixed (`chinaxiv:`, `yt:`, `tw:` …), degrade to `[]`, register one line in `SOURCES`.

## Open items — status 2026-07-04 (executor is UNBLOCKED for Phases 0–5)

1.  ✅ **Professor list, YouTube channels, podcast feeds** — planner-chosen starter lists in
    `~/workspace/EXECUTOR_INPUTS.md` on the server (user may edit anytime).
2.  ✅ **`YOUTUBE_API_KEY`** placed in `digest.env` (len 39, verified); user restricted it to
    YouTube Data API v3.
3.  ✅ **`TAVILY_API_KEY`** placed in `digest.env` (len 57) and validated live — HTTP 200 on a
    test search 2026-07-04.
4.  ⏳ **Burner X credentials** (Phase 6 only) — build everything else; leave the Twikit adapter
    unregistered until `TWIKIT_*` vars appear in `digest.env`.

**Executor access:** server `root@204.168.167.145`, run work as user `openclaw`; this plan is
mirrored at `~/workspace/PLAN.md`; inputs at `~/workspace/EXECUTOR_INPUTS.md`; secrets in
`/home/openclaw/.openclaw/digest.env` (user accepts key-exposure risk — hobby app, sandbox server —
but still: never print values, verify by length). Snapshot any file before patching
(`cp f f.pre-<tag>.$(date +%s)`) — the existing codebase convention.