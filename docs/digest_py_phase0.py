#!/usr/bin/env python3
"""digest.py — Priorities-driven multi-source literature digest.

Reads per-project priority docs from  ~/notes/Literature/*.md  (the ones the
/distill-priorities skill writes), builds queries from each doc's priority
table, fetches from arXiv + OpenAlex, dedups against state, scores relevance,
and posts each paper to the Discord channel its topic routes to. A roll-up
header goes to #briefing.

This replaces the old hardcoded-query arxiv_digest.py. Queries + routing now
live in the repo docs, so recommendations track the work automatically.

Dry-run:  python3 digest.py --dry-run   (prints routing, posts nothing)
"""

import urllib.request
import urllib.error
import urllib.parse
import ssl
import xml.etree.ElementTree as ET
import json
import datetime
import time
import re
import sys
import os
import argparse
import traceback
from pathlib import Path
from collections import defaultdict

import channels

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

# ── Paths / config ────────────────────────────────────────────────────────────
HOME = Path.home()
NOTES_DIR = Path(os.environ.get("LIT_NOTES_DIR", HOME / "notes" / "Literature"))
STATE_PATH = Path(__file__).resolve().parent / "digest_state.json"
CONFIG_PATH = HOME / ".openclaw" / "openclaw.json"

# Single source of truth for channel name -> ID lives in channels.py.
CHANNELS = channels.CHANNELS
BRIEFING_CHANNEL = channels.BRIEFING_ID
FALLBACK_CHANNEL = CHANNELS["literature"]

# Per-run caps (keep the channel readable)
MAX_TOTAL = 14
MIN_INSPIRATION = 2          # guaranteed #inspiration slots/day
MAX_PER_CHANNEL = 3
MAX_PER_TOPIC = 2
FETCH_PER_SOURCE = 8          # results pulled per topic per source
RECENT_DAYS = 120             # ignore papers older than this (freshness)
ARXIV_DELAY = 3.5             # arXiv asks ≥3 s between requests
POLITE_MAILTO = "chajadineyouss@gmail.com"   # OpenAlex polite pool
OPENALEX_KEY = os.environ.get("OPENALEX_API_KEY", "")   # authenticated = no 503s
IEEE_KEY = os.environ.get("IEEE_API_KEY", "")            # IEEE Xplore Metadata Search (200/day)
IEEE_ENABLED = os.environ.get("IEEE_ENABLED", "0").lower() not in ("0", "false", "no", "")  # set 1 once IEEE approves

RELEVANCE_EMOJI = {"HIGH": "🔴", "MEDIUM": "🟡", "GENERAL": "⚪"}
RELEVANCE_RANK = {"HIGH": 0, "MEDIUM": 1, "GENERAL": 2}

ARXIV_BASE = "http://export.arxiv.org/api/query"       # http (https is reset from this host)
OPENALEX_BASE = "https://api.openalex.org/works"
IEEE_BASE = "https://ieeexploreapi.ieee.org/api/v1/search/articles"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}

# Discord hard cap per message (2k for safety under the 4k documented limit)
DISCORD_MAX = 2000


def http_get(url, headers=None, tries=3, backoff=4.0):
    """GET with retry/backoff on transient 429/503; returns bytes or None."""
    headers = headers or {}
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=25, context=SSL_CTX) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt < tries - 1:
                wait = backoff * (attempt + 1)
                print(f"    [retry] HTTP {e.code}, waiting {wait:.0f}s...")
                time.sleep(wait)
                continue
            print(f"    [WARN] HTTP {e.code} for {url[:70]}...")
            return None
        except Exception as e:
            print(f"    [WARN] {type(e).__name__}: {e}")
            return None
    return None


# ── Priority-doc parsing ──────────────────────────────────────────────────────
def parse_priority_doc(path):
    """Extract (rank, topic, [search_terms], channel) rows from a doc's priority table."""
    text = path.read_text(encoding="utf-8", errors="replace")
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 5:
            continue
        if not cells[0].isdigit():          # skip header / separator rows
            continue
        rank = int(cells[0])
        topic = cells[1]
        terms = re.findall(r"`([^`]+)`", cells[3])   # search terms are in backticks
        route = cells[4].lstrip("#").strip()
        if not terms:
            continue
        rows.append({"rank": rank, "topic": topic, "terms": terms,
                     "channel": route, "slug": path.stem})
    return rows


def load_all_priorities():
    if not NOTES_DIR.exists():
        return []
    docs = []
    for p in sorted(NOTES_DIR.glob("*.md")):
        if p.stem == "_index":
            continue
        docs.extend(parse_priority_doc(p))
    return docs


# ── Term helpers ──────────────────────────────────────────────────────────────
def parse_term(raw):
    """Split one doc search-term into {phrases, authors, words}.

    e.g.  '"model reference adaptive control" quadrotor'
          -> phrases=['model reference adaptive control'], words=['quadrotor']
          'author:Lavretsky' -> authors=['Lavretsky']
    """
    phrases = re.findall(r'"([^"]+)"', raw)
    rest = re.sub(r'"[^"]+"', " ", raw)
    authors = re.findall(r'author:(\S+)', rest)
    rest = re.sub(r'author:\S+', " ", rest)
    words = [w for w in rest.split() if len(w) > 1]
    return {"phrases": phrases, "authors": authors, "words": words}


def clean_term(t):
    """Flatten a term to plain text (for OpenAlex free-text search)."""
    p = parse_term(t)
    return " ".join(p["phrases"] + p["words"]).strip()


def to_arxiv_query(terms):
    """arXiv query: each term -> (phrase AND word AND au:x); terms OR-joined."""
    clauses = []
    for raw in terms[:4]:                       # cap breadth per topic
        p = parse_term(raw)
        parts = [f'all:"{ph}"' for ph in p["phrases"]]
        parts += [f"au:{a}" for a in p["authors"]]
        parts += [f"all:{w}" for w in p["words"]]
        if parts:
            clauses.append("(" + " AND ".join(parts) + ")")
    return " OR ".join(clauses)


# ── Fetchers ──────────────────────────────────────────────────────────────────
def fetch_arxiv(terms, n=FETCH_PER_SOURCE):
    params = urllib.parse.urlencode({
        "search_query": to_arxiv_query(terms), "start": 0, "max_results": n,
        "sortBy": "submittedDate", "sortOrder": "descending"})
    body = http_get(f"{ARXIV_BASE}?{params}",
                    headers={"User-Agent": "openclaw-digest/2.0"})
    if not body:
        return []
    try:
        root = ET.fromstring(body)
    except Exception as e:
        print(f"    [WARN] arxiv parse failed: {e}")
        return []
    out = []
    for e in root.findall("atom:entry", ATOM_NS):
        t = e.find("atom:title", ATOM_NS)
        s = e.find("atom:summary", ATOM_NS)
        i = e.find("atom:id", ATOM_NS)
        pub = e.find("atom:published", ATOM_NS)
        if t is None or i is None:
            continue
        authors = [a.find("atom:name", ATOM_NS).text
                   for a in e.findall("atom:author", ATOM_NS)
                   if a.find("atom:name", ATOM_NS) is not None]
        if not (t.text and i.text):
            continue
        out.append({
            "id": f"arxiv:{i.text.strip().rsplit('/', 1)[-1]}",
            "title": re.sub(r"\s+", " ", t.text).strip(),
            "abstract": (s.text or "").strip()[:600],
            "url": i.text.strip(),
            "authors": authors,
            "date": (pub.text or "")[:10],
            "source": "arXiv",
        })
    return out


def _openalex_abstract(inv):
    if not inv:
        return ""
    pos = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos))


def fetch_openalex(terms, n=FETCH_PER_SOURCE):
    since = (datetime.date.today() - datetime.timedelta(days=RECENT_DAYS)).isoformat()
    q = {"search": " ".join(clean_term(t) for t in terms[:3]),
         "sort": "publication_date:desc", "per-page": n,
         "filter": f"from_publication_date:{since}", "mailto": POLITE_MAILTO}
    if OPENALEX_KEY:
        q["api_key"] = OPENALEX_KEY
    params = urllib.parse.urlencode(q)
    body = http_get(f"{OPENALEX_BASE}?{params}",
                    headers={"User-Agent": f"openclaw-digest/2.0 (mailto:{POLITE_MAILTO})"})
    if not body:
        return []
    try:
        data = json.loads(body)
    except Exception as e:
        print(f"    [WARN] openalex parse failed: {e}")
        return []
    out = []
    for w in data.get("results", []):
        doi = w.get("doi") or w.get("id", "")
        title = w.get("title") or ""
        if not title:
            continue
        authors = [a["author"]["display_name"]
                   for a in w.get("authorships", [])[:3] if a.get("author")]
        out.append({
            "id": f"openalex:{doi}",
            "title": re.sub(r"\s+", " ", title).strip(),
            "abstract": _openalex_abstract(w.get("abstract_inverted_index"))[:600],
            "url": w.get("doi") or w.get("id", ""),
            "authors": authors,
            "date": w.get("publication_date", ""),
            "source": "OpenAlex",
        })
    return out


# ── Relevance scoring ─────────────────────────────────────────────────────────
def _ieee_query(terms):
    phrases = []
    for raw in terms:
        p = parse_term(raw)
        phrases += [f'"{ph}"' for ph in p["phrases"]]
    if not phrases:
        for raw in terms:
            phrases += parse_term(raw)["words"]
    return " OR ".join(list(dict.fromkeys(phrases))[:6])


def fetch_ieee(terms, n=FETCH_PER_SOURCE):
    """IEEE Xplore Metadata Search. Gated on IEEE_KEY; graceful [] on any failure."""
    if not IEEE_KEY:
        return []
    q = _ieee_query(terms)
    if not q:
        return []
    params = urllib.parse.urlencode({
        "apikey": IEEE_KEY, "format": "json", "querytext": q,
        "max_records": min(n, 25), "start_record": 1,
        "sort_field": "publication_year", "sort_order": "desc",
    })
    body = http_get(f"{IEEE_BASE}?{params}")
    if not body:
        return []
    try:
        data = json.loads(body)
    except Exception as e:
        print(f"    [WARN] ieee parse failed: {e}")
        return []
    out = []
    for a in data.get("articles", []):
        doi = a.get("doi") or a.get("article_number") or ""
        au = a.get("authors", {})
        authors = ([x.get("full_name", "") for x in au.get("authors", [])]
                   if isinstance(au, dict) else [])
        authors = [x for x in authors if x]
        year = str(a.get("publication_year") or "")[:4]
        url = (a.get("html_url") or a.get("pdf_url")
               or (f"https://doi.org/{doi}" if "/" in str(doi) else ""))
        out.append({
            "id": f"ieee:{doi or a.get('title','')[:40]}",
            "title": (a.get("title") or "").strip(),
            "abstract": (a.get("abstract") or "")[:600],
            "authors": authors,
            "date": f"{year}-01-01" if year else "",
            "source": "IEEE",
            "url": url,
        })
    return out[:n]


def score(paper, terms):
    """HIGH if a distinctive topic phrase is in the title, MEDIUM if in the abstract."""
    title = paper["title"].lower()
    abstract = paper["abstract"].lower()
    tier = "GENERAL"
    for raw in terms:
        p = parse_term(raw)
        for ph in p["phrases"]:             # distinctive multi-word phrases
            ph = ph.lower()
            if ph in title:
                return "HIGH"
            if ph in abstract:
                tier = "MEDIUM"
        for w in p["words"]:                # single keyword — weaker signal
            if w.lower() in title and tier == "GENERAL":
                tier = "MEDIUM"
    return tier


# ── Collection ────────────────────────────────────────────────────────────────
def roundrobin(*lists):
    """Fair merge of N source lists so each source gets represented under the cap."""
    lists = [l for l in lists if l]
    out = []
    if not lists:
        return out
    for i in range(max(len(l) for l in lists)):
        for l in lists:
            if i < len(l):
                out.append(l[i])
    return out


def collect(priorities, posted, wide=False):
    per_topic_cap = 4 if wide else MAX_PER_TOPIC
    candidates = []
    seen = set()
    for topic in sorted(priorities, key=lambda r: r["rank"]):
        a = fetch_arxiv(topic["terms"])
        time.sleep(ARXIV_DELAY)             # arXiv politeness (≥3 s between calls)
        o = fetch_openalex(topic["terms"])
        sources = [a, o]
        if IEEE_KEY and IEEE_ENABLED:
            sources.append(fetch_ieee(topic["terms"]))
        try:
            import extra_sources as _X          # RSS/blogs + HN + Crossref preprints
            sources.extend(_X.fetch_all(topic["terms"], FETCH_PER_SOURCE))
        except Exception as e:
            print(f"    [xsrc] disabled: {e}")
        found = roundrobin(*sources)        # fair mix: preprint + OA journal + IEEE
        time.sleep(1)
        kept = 0
        for p in found:
            if p["id"] in posted or p["id"] in seen:
                continue
            if kept >= per_topic_cap:
                break
            seen.add(p["id"])
            p["relevance"] = score(p, topic["terms"])
            p["topic"] = topic["topic"]
            p["channel"] = topic["channel"]
            p["rank"] = topic["rank"]
            candidates.append(p)
            kept += 1
    # HIGH first, then by topic rank, then by date desc
    candidates.sort(key=lambda p: (RELEVANCE_RANK[p["relevance"]], p["rank"], -_datekey(p)))
    if wide:
        return candidates                      # full pool for the LLM quality layer
    return apply_caps(candidates)


def apply_caps(candidates):
    """Global + per-channel caps (keyword-path selection / LLM fallback)."""
    per_chan = defaultdict(int)
    selected = []
    for p in candidates:
        if len(selected) >= MAX_TOTAL:
            break
        if per_chan[p["channel"]] >= MAX_PER_CHANNEL:
            continue
        per_chan[p["channel"]] += 1
        selected.append(p)
    return selected


def _datekey(p):
    try:
        return int(p["date"].replace("-", ""))
    except Exception:
        return 0


# ── State ─────────────────────────────────────────────────────────────────────
def load_state():
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"posted_ids": []}


def save_state(state):
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Discord ───────────────────────────────────────────────────────────────────
def read_token():
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return data.get("channels", {}).get("discord", {}).get("token", "")


def post_discord(channel_id, content, token):
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    req = urllib.request.Request(
        url, data=json.dumps({"content": content}).encode("utf-8"),
        headers={"Authorization": f"Bot {token}", "Content-Type": "application/json",
                 "User-Agent": "openclaw-digest/2.0"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status
    except urllib.error.HTTPError as e:
        print(f"    [ERROR] HTTP {e.code}: {e.read().decode('utf-8','replace')[:200]}")
        return e.code


def format_paper(p):
    """Format one paper for Discord. Returns a str (≤ DISCORD_MAX) or a list of
    strs if the content must be split across multiple messages."""
    emoji = RELEVANCE_EMOJI[p["relevance"]]
    authors = ", ".join(p["authors"]) if p["authors"] else "Unknown"
    note_line = (f"**Why it matters:** {p['note']}\n"
                 if p.get("note") else "")
    body = (
        f"{emoji} **{p['title']}**\n"
        f"**Topic:** {p['topic']}  •  **Source:** {p['source']}  •  {p['date']}\n"
        f"**Authors:** {authors}\n"
        f"**Abstract:** {p['abstract'][:450]}{'…' if len(p['abstract'])>450 else ''}\n"
        f"**Link:** <{p['url']}>\n"
        f"{note_line}"
        f"[topic: {p['channel']}] [relevance: {p['relevance'].lower()}] [status: skimmed]"
    )
    if len(body) <= DISCORD_MAX:
        return body
    return _split_paper_message(p, emoji, authors, note_line)


def _split_paper_message(p, emoji, authors, note_line):
    """Split an over-long paper into ≤ DISCORD_MAX chunks (header → body chunks)."""
    head = (
        f"{emoji} **{p['title']}**\n"
        f"**Topic:** {p['topic']}  •  **Source:** {p['source']}  •  {p['date']}\n"
        f"**Authors:** {authors}\n"
        f"**Link:** <{p['url']}>"
    )
    abstract = p["abstract"] or ""
    tail = (
        f"{note_line}"
        f"[topic: {p['channel']}] [relevance: {p['relevance'].lower()}] [status: skimmed]"
    )
    head_overhead = len(head) + 1          # +1 for newline
    tail_overhead = len(tail) + 1
    avail = DISCORD_MAX - head_overhead - tail_overhead - len("\n…[abstract truncated]")
    chunks = []
    if avail > 100:
        truncated = abstract[:avail] + ("…" if len(abstract) > avail else "")
        chunks.append(head + "\n**Abstract:** " + truncated + "\n" + tail)
    else:
        # pathological: just truncate the title
        chunks.append((head + "\n" + tail)[:DISCORD_MAX])
    return chunks


def ensure_inspiration_floor(selected, pool, floor, channel="inspiration"):
    """Guarantee >=floor cross-field items reach #inspiration. The reviewer is
    conservative and the LLM path has no per-channel floor, so top up from the
    best un-selected pool candidates whose topic routes to #inspiration."""
    have = [p for p in selected if p.get("channel") == channel]
    if len(have) >= floor:
        return selected
    chosen = {p["id"] for p in selected}
    extras = [p for p in pool if p.get("channel") == channel and p["id"] not in chosen]
    for p in extras[: floor - len(have)]:
        p = dict(p)
        p.setdefault("relevance", "GENERAL")
        p["channel"] = channel
        p.setdefault("note", "cross-field inspiration pick")
        selected.append(p)
        print("    [floor] +inspiration: " + p["title"][:60])
    return selected


# ── Crash reporting ───────────────────────────────────────────────────────────
def _post_crash_report(exc):
    """Best-effort: post a short crash notice to #briefing. Failures are silent."""
    try:
        token = read_token()
        if not token:
            print("    [crash] no token; skipping crash post")
            return
        tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
        last = "".join(tb).strip().splitlines()[-3:]   # last 3 lines is enough
        msg = (
            f"## ⚠️ digest.py crash — {datetime.date.today().isoformat()}\n"
            f"**Error:** `{type(exc).__name__}: {exc}`\n"
            f"```\n" + "\n".join(last) + "\n```"
        )
        # hard-cap below DISCORD_MAX
        if len(msg) > DISCORD_MAX:
            msg = msg[:DISCORD_MAX - 50] + "\n…[truncated]"
        print(f"    [crash] posting crash report to #briefing")
        post_discord(BRIEFING_CHANNEL, msg, token)
    except Exception as inner:
        # last-ditch: do not let the crash handler itself crash
        print(f"    [crash] crash-report FAILED: {type(inner).__name__}: {inner}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    try:
        _run()
    except SystemExit:
        raise
    except BaseException as e:                       # noqa: BLE001 (top-level guard)
        print(f"[CRASH] uncaught {type(e).__name__}: {e}")
        traceback.print_exc()
        _post_crash_report(e)
        sys.exit(1)


def _run():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print routing, post nothing")
    args = ap.parse_args()

    today = datetime.date.today().isoformat()
    print(f"[digest] {today}  (dry-run={args.dry_run})")

    priorities = load_all_priorities()
    if not priorities:
        print(f"[ERROR] no priority docs in {NOTES_DIR}")
        sys.exit(1)
    slugs = sorted({r["slug"] for r in priorities})
    print(f"[1] loaded {len(priorities)} topics from {slugs}")

    state = load_state()
    posted = set(state.get("posted_ids", []))
    llm_on = bool(os.environ.get("OPENROUTER_API_KEY"))
    print(f"[2] fetching (arXiv + OpenAlex), {len(posted)} already seen... (llm={'on' if llm_on else 'off'})")
    pool = collect(priorities, posted, wide=llm_on)
    if llm_on:
        selected = None
        try:
            import llm_layer
            print(f"[2b] LLM quality layer: {len(pool)} candidates -> "
                  f"{len(llm_layer.WORKERS)} free workers -> reviewer {llm_layer.REVIEWER}")
            selected = llm_layer.rerank(pool, priorities, MAX_TOTAL, CHANNELS)
        except Exception as e:
            print(f"    [llm] layer error, falling back to keyword ranking: {e}")
        if not selected:
            print("    [llm] no LLM result -> keyword caps")
            selected = apply_caps(pool)
    else:
        selected = pool
    selected = ensure_inspiration_floor(selected, pool, MIN_INSPIRATION)
    print(f"    -> {len(selected)} new papers selected")
    if not selected:
        print("[done] nothing new.")
        return

    by_chan = defaultdict(list)
    for p in selected:
        by_chan[p["channel"]].append(p)

    # roll-up header -> #briefing
    hi = sum(1 for p in selected if p["relevance"] == "HIGH")
    med = sum(1 for p in selected if p["relevance"] == "MEDIUM")
    gen = sum(1 for p in selected if p["relevance"] == "GENERAL")
    routes = "  ".join(f"#{c}: {len(v)}" for c, v in sorted(by_chan.items()))
    header = (
        f"## 📚 Literature Digest — {today}\n"
        f"**{len(selected)} papers** • 🔴 {hi}  🟡 {med}  ⚪ {gen}\n"
        f"Routed → {routes}\n"
        f"Driven by `notes/Literature/` priorities ({', '.join(slugs)})"
    )

    if args.dry_run:
        print("\n===== DRY RUN =====")
        print(header)
        for c, papers in sorted(by_chan.items()):
            cid = CHANNELS.get(c, FALLBACK_CHANNEL)
            print(f"\n#### -> #{c} ({cid})")
            for p in papers:
                print(f"  {RELEVANCE_EMOJI[p['relevance']]} [{p['source']}] {p['title'][:80]}")
                print(f"     {p['url']}")
        return

    token = read_token()
    if not token:
        print("[ERROR] no discord token")
        sys.exit(1)

    print(f"[3] posting header -> #briefing")
    post_discord(BRIEFING_CHANNEL, header, token)

    newly = []
    for c, papers in sorted(by_chan.items()):
        cid = CHANNELS.get(c, FALLBACK_CHANNEL)
        print(f"[4] posting {len(papers)} -> #{c} ({cid})")
        for p in papers:
            msgs = format_paper(p)
            if isinstance(msgs, list):
                chunks = msgs
            else:
                chunks = [msgs]
            ok = True
            for ch in chunks:
                st = post_discord(cid, ch, token)
                if st not in (200, 201):
                    ok = False
                    print(f"    ✗ HTTP {st} — {p['title'][:60]}")
                time.sleep(0.8)
            if ok:
                newly.append(p["id"])
                print(f"    ✓ {p['relevance']} — {p['title'][:60]}")
            time.sleep(0.4)

    state["posted_ids"] = list(posted | set(newly))[-500:]   # keep last 500
    save_state(state)
    print(f"[done] posted {len(newly)} papers; state has {len(state['posted_ids'])} ids")


if __name__ == "__main__":
    main()
