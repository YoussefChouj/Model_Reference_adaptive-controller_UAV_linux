# What does the armcc conformance gate build, and how is it invoked safely?

Type: grilling
Status: open

## Question

The gcc harness in `API/tests/` executes firmware C on the host to check behaviour. It
cannot check dialect: gcc defaults to C99 and happily accepts code ARMCC V5.06 rejects —
mixed declarations and statements, VLAs, and differing `long long` and anonymous-union
handling. A change can pass the whole Python suite and then fail the only build that
matters.

The user's framing (2026-07-30): the build half of `rebuild_and_flash` already works and
is tested, so reuse it rather than inventing a second build path.

What to settle:

- **Whole-project or per-file?** UV4 `-r` rebuilds the project; there is no per-file entry
  point. A whole-project build is ~28 s and 0 errors today with 69 pre-existing warnings.
  Per-file conformance would mean invoking armcc directly with a hand-built include and
  define set, which becomes a second definition of the build that can itself drift.
- **Where it plugs in.** `tasks.py` `LANES` currently has livewatch, gui, sim, flight, sil,
  flashtool, budget. A gate that shells out to a 28 s Windows-only toolchain does not
  belong in the same lane as fast pure-Python tests, and it must skip cleanly where Keil
  is absent — the same courtesy `test_subscribe_c.py` extends when gcc is missing.
- **Warning policy.** 69 warnings are pre-existing. A gate that fails on any warning fails
  immediately; one that fails only on errors misses the dialect problems that surface as
  warnings. `ground_station/build_budget/` already tracks warning identities against a
  baseline — decide whether this gate defers to it or duplicates it.
- **Probe safety.** The gate must go through `rebuild_and_flash`'s build stage, which wraps
  `safe_flash._pMon_neutralised()`. A bare UV4 launch loads `<pMon>BIN\CMSIS_AGDI.dll`,
  claims the CMSIS-DAP probe and halts a powered core — it killed a live drone on
  2026-07-28. Do not hand-roll a UV4 invocation.
- **Artefact custody.** A build shifts RAM symbol addresses, and `OBJ/JX_FLY.axf` must keep
  matching the flashed image or livewatch and the flash safety gate resolve garbage. The
  gate must build without disturbing the committed artefact triple, or restore it. This is
  what `rebuild_and_flash`'s snapshot/restore already does — confirm it covers a
  build-without-flash path, since a known rework item is that the `all` gate-fail path
  exits without calling `artifact_custody.restore`.

Recommendation to argue against: whole-project via the existing build stage, its own lane,
skip where Keil is absent, fail on errors only and defer warning tracking to
`build_budget`.
