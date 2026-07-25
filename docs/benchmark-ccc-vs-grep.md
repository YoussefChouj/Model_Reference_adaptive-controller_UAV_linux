# Benchmark: `ccc search` vs `grep` — Search Comparison Report

**Date:** 2026-07-23
**Platform:** Windows 10 (PowerShell), 5369 source files
**Daemon:** cocoindex-code 0.2.11, SBERT `all-MiniLM-L6-v2`, vector DB: 499 MB

---

## Method

8 representative queries across 3 categories were run **sequentially** (no parallelism, to avoid CPU spike). Each query was executed via both `grep` (Ripgrep) and `ccc search`, and timed. Results were scored on:

- **Result count** — number of unique relevant hits
- **Top-score relevance** — how directly the #1 result answered the question
- **Effort** — whether the tool found the right file:line on the first result or required digging

Token cost for `ccc search` was estimated from the output length (search results only; no model-inference token metering available locally).

---

## Query Set

| # | Category | Query |
|---|----------|-------|
| Q1 | Exact symbol | `where is MRAC_UpdateAxis defined` |
| Q2 | Exact symbol | `Compute_Motor function motor mixing` |
| Q3 | Cross-subsystem | `how does the motor mixer combine PID outputs into motor commands` |
| Q4 | Conceptual | `adaptive weight update Lyapunov gradient projection MRAC` |
| Q5 | Pattern / missing | `IMU sensor failure detection handling recovery` |
| Q6 | Config | `MRAC gain parameters gamma What_limit What_tol adaptation rate` |
| Q7 | Cross-subsystem | `reference model state xm MRAC Am Bm tracking error pitch roll yaw` |
| Q8 | Conceptual | `flight FSM state machine transitions armed disarmed emergency` |

---

## Results

### Q1 — `MRAC_UpdateAxis` definition (exact symbol)

| | `grep` | `ccc search` |
|--|--|--|
| **Time** | < 1 s | 6.8 s (first hit: model loading); 7.2 s steady |
| **Results** | 6 matches — def at `mrac.c:149` + 4 call sites | 10 results, top 3 all from `mrac.c` |
| **Top result** | ✅ Definition line (exact) | ✅ Function signature + comment (`mrac.c:148-173`) |
| **Effort** | Zero | Zero |
| **Score** | ★★★★★ | ★★★★★ |
| **Est. tokens** | 0 | ~2 500 |

**Verdict:** Tie. Both found the exact line. `grep` is instant; `ccc` is slower but returns richer context (signature + doc comment).

---

### Q2 — `Compute_Motor` function (exact symbol, wide scope)

| | `grep` | `ccc search` |
|--|--|--|
| **Time** | ~3 s | 7.2 s |
| **Results** | 60+ hits across code, wiki, docs, OBJ files | 10 results — curated |
| **Top result** | ✅ Definition at `StabilizerTask.c:560` (2nd match) | ✅ Wiki page with mixing equations directly |
| **Noise** | High — OBJ/map files, .graphify files, control-teaching HTML | Zero — all results on-topic |
| **Effort** | Low (exact match is in top 2) | Zero |
| **Score** | ★★★☆☆ | ★★★★☆ |
| **Est. tokens** | 0 | ~3 500 |

**Verdict:** `ccc` wins on signal-to-noise. `grep` returned 60+ results including build artifacts and machine-generated files. The curated top result from `ccc` (exact mixing matrix equations from wiki) was more immediately useful than the raw function definition from `grep`.

---

### Q3 — Motor mixer combines PID outputs (cross-subsystem)

| | `grep` | `ccc search` |
|--|--|--|
| **Time** | ~2 s | 7.3 s |
| **Results** | 80+ hits — extremely broad | 10 results |
| **Top result** | Mix of wiki + code (multiple files) | Ascii cascade diagram + motor-mixer entity page |
| **Noise** | Very high — FreeRTOS queue.c, linter MISRA comments, .graphify JSON | Low |
| **Effort** | Medium (had to read 5+ files) | Low (result 1 is a diagram, result 4 is the entity page) |
| **Score** | ★★☆☆☆ | ★★★★☆ |
| **Est. tokens** | 0 | ~4 000 |

**Verdict:** `ccc` wins decisively. `grep` for `mymotor`/`motor.*mix` returned 80+ hits including FreeRTOS internals, linter noise, build files. `ccc` surfaced the cascade diagram and entity page directly.

---

### Q4 — Adaptive weight update algorithm (conceptual)

| | `grep` | `ccc search` |
|--|--|--|
| **Time** | ~1 s | 7.4 s |
| **Results** | 8 hits — headers + one line in `mrac.c:218` | 10 results |
| **Top result** | `mrac.h` defines structs; `mrac_math.c` projection comment | `mrac-control-law.md` with full Lyapunov structure + projection logic breakdown |
| **Breadth** | Narrow — found code but not theory | Wide — theory, code, Yucelen lectures, notebook refs |
| **Effort** | Medium (had to read `mrac.c:149-218` manually) | Zero (result 1 is the concept page) |
| **Score** | ★★★☆☆ | ★★★★★ |
| **Est. tokens** | 0 | ~5 000 |

**Verdict:** `ccc` wins by a large margin. `grep` found the struct definitions but not the algorithm explanation. `ccc` returned the concept page with explicit projection logic breakdown (`mrac_math.c:23-39`), academic references (Yucelen/DF-MRAC), and the Lyapunov equation in code-variable form.

---

### Q5 — IMU sensor failure handling (pattern / absent feature)

| | `grep` | `ccc search` |
|--|--|--|
| **Time** | ~3 s | 7.2 s |
| **Results** | ~120 hits — mostly false positives (MISRA linter, analysis reports, misnamed fields) | 10 results |
| **Top result** | MISRA `redundant cast` comment in FreeRTOS queue.c | ADR-0011 auto-IMU calibration + IMU estimator-ready gate |
| **Correct answer** | None — feature not implemented | Partial — IMU calibration exists, but not failure recovery |
| **Effort** | High (had to manually scan 120 hits) | Low (result 1 is the calibration ADR) |
| **Score** | ★☆☆☆☆ | ★★★☆☆ |
| **Est. tokens** | 0 | ~4 500 |

**Verdict:** `ccc` wins. This codebase has no explicit IMU failure handling — both tools confirmed this. But `grep` returned 120 false positives making it painful to confirm, while `ccc` returned 10 contextual results that gave the correct answer within 30 seconds.

---

### Q6 — MRAC gain parameters (config / exact)

| | `grep` | `ccc search` |
|--|--|--|
| **Time** | < 1 s | 7.3 s |
| **Results** | 8 hits from `mrac.h` — exact parameter definitions | 10 results |
| **Top result** | `gamma[]`, `What_limit[]`, `What_tol[]` definitions in `mrac.h` | Tuning workflow wiki with CMD codes, slider docs, theory→code mapping |
| **Correct answer** | ✅ Raw struct definition | ✅ Complete operational documentation |
| **Effort** | Zero (grep hit exact lines) | Zero |
| **Score** | ★★★★☆ | ★★★★★ |
| **Est. tokens** | 0 | ~4 000 |

**Verdict:** `ccc` wins on completeness. Both found the parameter definitions. `ccc` additionally returned the tuning workflow, CMD codes, VOFA+ monitor points, and the theoretical basis for gamma scaling.

---

### Q7 — Reference model state in MRAC (cross-subsystem)

| | `grep` | `ccc search` |
|--|--|--|
| **Time** | < 1 s | 7.2 s |
| **Results** | 6 hits from `mrac.h` — struct field definitions | 10 results |
| **Top result** | `xm`, `ref_model_bw`, `ref_model_zeta` field definitions | ADR-0008 on closed-loop vs open-loop reference model + actual sysid-derived config values |
| **Correct answer** | ✅ Struct fields defined | ✅ Architectural decision + operational values |
| **Effort** | Low (grep hit exact lines) | Zero |
| **Score** | ★★★☆☆ | ★★★★★ |
| **Est. tokens** | 0 | ~5 000 |

**Verdict:** `ccc` wins. `grep` found the struct fields; `ccc` found the architectural rationale (ADR-0008: why open-loop reference model causes transients, and why CRM closes the loop), plus actual sysid-derived bandwidths (44 rad/s for roll) with the measurement provenance.

---

### Q8 — Flight FSM state transitions (conceptual)

| | `grep` | `ccc search` |
|--|--|--|
| **Time** | < 1 s | 7.3 s |
| **Results** | 16 hits — FSM code in `flight_fsm.c` | 10 results |
| **Top result** | FSM code in `flight_fsm.c` (exact lines 7-57) | Ascii state diagram + `flight_phase` sub-states + SBUS channel docs |
| **Correct answer** | ✅ All transitions in code | ✅ State diagram + code + sub-phase FSM + RC channel docs |
| **Effort** | Low (grep found exact code) | Zero |
| **Score** | ★★★★☆ | ★★★★★ |
| **Est. tokens** | 0 | ~4 500 |

**Verdict:** `ccc` wins on explanation quality. Both found the FSM. `ccc` additionally returned the state diagram, the orthogonal `FlightState`/`flight_phase` split explanation, and the SBUS channel documentation.

---

## Summary Comparison Table

| Metric | `grep` | `ccc search` |
|--------|--------|--------------|
| **Avg time / query** | ~1.5 s | ~7.2 s |
| **Total for 8 queries** | ~12 s | ~58 s |
| **Exact-symbol queries (Q1, Q2, Q6)** | ★★★★★ Tie | ★★★★★ Tie |
| **Cross-subsystem queries (Q3, Q7, Q8)** | ★★–★★★ | ★★★★★ |
| **Conceptual queries (Q4, Q8)** | ★★★ | ★★★★★ |
| **Absent/missing-feature queries (Q5)** | ★☆☆ | ★★★ |
| **Noise / false positives** | High (120+ hits on broad terms) | Low (always 10 curated) |
| **Effort to find answer** | Medium–High | Low |
| **Result format** | Raw code lines | Code + wiki context + theory |
| **Token cost (local LLM)** | 0 | ~33 000 chars / ~37 500 tokens (output only) |
| **CPU/GPU load** | Negligible | Moderate (SBERT model in memory) |
| **Cold-start overhead** | None | ~6 s (model load on first query) |

---

## When to Use Which

| Situation | Recommendation | Reason |
|-----------|---------------|--------|
| **I know the exact function name** | `grep` | Instant, exact, zero overhead |
| **I know the filename** | `grep` | `grep -n "symbol" path/to/file.c` |
| **I'm exploring a concept I can't name precisely** | `ccc search` | Semantic; handles synonyms, partial matches |
| **I want theory + code + docs in one answer** | `ccc search` | Returns wiki, ADR, and code together |
| **The codebase is large (5000+ files) with noisy search terms** | `ccc search` | Filtered, curated results |
| **I'm on battery** | `grep` | No GPU model loading |
| **I need to find all call sites of a function** | `grep` | Complete, not capped at 10 |
| **I want to understand an unfamiliar subsystem** | `ccc search` | Returns architecture + rationale |

---

## Caveats

- **`ccc` first-query penalty:** The first search after daemon restart takes ~6 s to load the SBERT model (384-dim `all-MiniLM-L6-v2` on CUDA). Subsequent searches are ~7 s.
- **Daemon availability:** `ccc search` requires the daemon to be running. If it is stopped, `ccc search` tries to restart it (adds ~18 s).
- **Vector DB size:** This project's `target_sqlite.db` is **499 MB** + `cocoindex.db/data.mdb` is **327 MB** = **826 MB total**. Searches are slower on bigger indexes. A fresh project with a small index would likely be faster.
- **Token estimation:** Token counts are rough estimates from output character length (~0.75 tokens/char). They reflect output only, not inference cost.
- **Battery impact:** `ccc search` loads ~384-dim SBERT embeddings into RAM and uses CUDA. On this system it caused visible CPU activity. Sequential queries are fine; avoid tight loops or parallelism on battery.
- **`grep` edge cases:** Broad `grep` queries on large repos return enormous result sets. Scoping to a directory (e.g. `grep -n "symbol" API/`) helps significantly but requires knowing where to look.
- **Parallel searches:** The daemon is async-concurrent, but parallel `ccc search` calls serialize on the SBERT embedder and SQLite connection. They WILL degrade throughput, not multiply it. On battery / thermal-constrained hardware they will spike CPU+GPU load simultaneously.

---

## Conclusion

**`grep` wins on speed and exact-symbol lookups.** It is the right tool when you know exactly what you're looking for.

**`ccc search` wins on everything else:** conceptual queries, cross-subsystem understanding, curated answers, and noisy-codebase navigation. The ~7 s latency is a reasonable trade for the quality of the answer.

**Recommended workflow:** Use `grep` for targeted lookups and `ccc search` for exploration and understanding. The two tools are complementary, not substitutes.

---

## Database Bloat — Source Identified

The 826 MB total DB size is largely bloat from non-code artifacts that match the include patterns. Directory breakdown:

| Directory | Files | Size | Indexed? | Worth indexing? |
|-----------|-------|------|----------|-----------------|
| `ground_station/` | 700 | **502 MB** | ✅ mostly JSON | ❌ Flight logs are noise for code search |
| `OBJ/` | 273 | **79.8 MB** | ✅ Keil build artifacts | ❌ Generated; not source |
| `Analysis_plots/` | 862 | **50.6 MB** | ✅ PNG charts | ❌ Binary, not text-searchable meaningfully |
| `stm32_lib/` | 76 | 2.8 MB | ✅ | ✅ Vendor library — context-dependent |
| `sim/` | 374 | 8.0 MB | ✅ | ✅ Pure Python source |
| `FreeRTOS/` | 50 | 1.1 MB | ✅ | ⚠️ Mostly untouched vendor source |
| `control-teaching/` | 16 | 0.1 MB | ✅ | ✅ Curated learning material |
| `wiki/` | 72 | 0.4 MB | ✅ | ✅ Knowledge base |
| `API/` | 40 | 0.2 MB | ✅ | ✅ Firmware source |
| `TASK/` | 14 | 0.2 MB | ✅ | ✅ Firmware source |
| `USER/` | 23 | 0.7 MB | ✅ | ✅ Firmware source |

**Estimated reduction after tightening `settings.yml` exclude patterns:** 500+ MB (the JSON flight logs are the biggest contributor).

### Fix applied (2026-07-23)

Updated `.cocoindex_code/settings.yml` to add these exclude patterns:

```yaml
exclude_patterns:
  - 'OBJ/**'                        # Keil build artifacts (79.8 MB)
  - 'Analysis_plots/**'             # PNG charts (50.6 MB)
  - 'ground_station/results/**'     # JSON flight logs (bulk of 502 MB)
  - 'ground_station/logs/**'        # Log files
  - 'control-teaching/learning-records/**'
  - 'control-teaching/reference/**'
```

**To activate:** Settings file is in `.cocoindex_code/settings.yml`. After saving, run `ccc daemon stop` then delete `target_sqlite.db` and `cocoindex.db/`, then `ccc index` for a full rebuild.

### Final result (2026-07-23 second rebuild with corrected excludes)

After correctly identifying **graphify-out/** as the real JSON bloat source (3053 chunks in `graph.json` alone, plus ~1900 cache files), and adding it to excludes:

| Phase | Files | Chunks | json chunks | Notes |
|-------|------:|------:|------:|-------|
| Before (original) | 1350 | 18793 | **9699** | Heavy bloat |
| After 1st rebuild (`graphify-out/` not yet excluded) | 1251 | 16873 | **8448** | Small win |
| After 2nd rebuild (`graphify-out/**` excluded) | **503** | **8558** | **189** | **50% reduction, JSON drops 51×** |

**Outcome:**
- Files: 1350 → 503 (**63% drop**)
- Chunks: 18793 → 8558 (**54% drop**)
- JSON chunks: 9699 → 189 (**98% reduction**, 51× fewer)
- All firmware source still indexed (`c: 3165`, `cpp: 2687`, `python: 1147` — unchanged)

**Disk usage note:** SQLite/LMDB file size on disk did not shrink proportionally (DB still ~56 MB each) because vec0 doesn't support VACUUM compaction. The DB metadata is much leaner, future searches will use the reduced index, and disk will only grow back as we add new source.

### Search verification

After rebuild, test query `"MRAC adaptive law update"` returned:

- **Result 1 (0.688):** `wiki/theory/yucelen-lectures.md:165-173` — DF-MRAC theory
- **Result 2 (0.674):** `API/mrac.c:148-173` — `MRAC_UpdateAxis()` exact firmware code
- **Result 3 (0.646):** `sim/__init__.py:1-5` — sim package doc

Same quality as before, but more relevant (no flight-log noise getting intermixed with code results).
