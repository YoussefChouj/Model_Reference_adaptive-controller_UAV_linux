# Streaming subscription session (2026-07-29)

> Moved verbatim out of CLAUDE.md on 2026-08-09 to cut per-turn
> context churn. CLAUDE.md keeps a compact index pointing here.

### Streaming Subscription Session (2026-07-29) — superseded above, still valid background

**What it is**: CMD `0x21` subscribe on UART5 → `0x08` schema reply → `0x09+slot` data frames on the chosen transport. Range tuples `(address, size, count)`, schema sent once, values only in data frames. Wire layout pinned in `API/subscribe.h` (read its header comment first — it is the contract).

**Shipped and verified ON THE DRONE (single-slot build, flashed 20:43)**:
- 142 rows / 23 columns / **0 dropped, 0 gaps**, live `mrac_state.roll.Theta` visibly adapting
- Control plane: 0x08 schema echo, 0x7F on over-budget, bad-CRC silently dropped, stop works
- Costs ~4% of frame 0x01 and nothing else

**Multi-rate slots — FLASHED AND VERIFIED ON THE DRONE (2026-07-29 07:45)**:
- Default frame (20/10/5 Hz, 3 slots) over 30 s: **0 dropped, 0 malformed on every slot**; CSVs in `logs/multislot_final.slot{0,1,2}.csv`
- `Code=81348 RW-data=2388 ZI-data=113356`. First flash attempt died with `Programming Failed!RDDI-DAP Error` (part erased, drone dark); a plain retry fixed it — see memory `project_headless_build_unreliable`
- **Measured ceiling**: the firmware permits 2304 B/s on UART5 but only ~1600 B/s arrives intact. 2055 B/s was accepted and dropped 14 % on every slot; 1580 B/s ran clean. Single-slot runs never dropped, so it is bandwidth, not the scheduler. Memory `project_stream_frame_budget`
- **New, all tested (466 green)**: `ground_station/flashtool/rebuild_and_flash.py` (one-command build+flash, per-stage exit codes, `--yes` required to flash, snapshots + restores the artifact triple, retries RDDI-DAP), `ground_station/flashtool/target_power.py` (listens for 0xAA 0xBB to decide powered/dark), `ground_station/livewatch/log_frames.md` (**the default frame — a Markdown table; editing it needs no rebuild**), `.claude/skills/stream-log/SKILL.md`
- Its frontmatter `description:` is stale (still says power-sequencing hazard); the body is correct. Edits to that line were blocked by the tool-permission classifier — needs a human to fix, cosmetic only

Original code-complete notes:
- `API/subscribe.h` — `SUBSCRIBE_MAX_SLOTS 4`; request payload now `3 + N*8` (divider, transport, **slot**); schema payload `5 + N*8`; data frame type = `0x09 + slot`
- `API/subscribe.c` — `s_streams[4]` + `s_rr` cursor; `Subscribe_StreamTick` marks due slots then serves **one per cycle round-robin**; `Subscribe_StreamBps()`; budget guard **sums all slots** via new `other_bps_uart5`/`other_bps_usart3` params
- `BSP/usart5.c:197` — IRQ length check `(payload_len - 3) % 8`
- `ground_station/livewatch/stream.py` — `MAX_SLOTS`, `MultiStreamDecoder`, `stream_bps`, `StreamSchema.slot/.data_frame_type`
- `ground_station/livewatch/stream_log.py` — `--group "RATE:sym:N,sym:N"` (up to 4), one CSV per slot
- **373 tests pass.** Plus `API/tests/test_subscribe_harness.c` — compiles the real firmware C with gcc `-m32` and asserts the scheduler: 80 ticks → exactly 10 slow-slot + 70 fast-slot frames, one per tick, gap-free per-slot sequences, busy-DMA skips cleanly. Run via `ground_station/livewatch/tests/test_subscribe_c.py`.

**Protocol v2 — FLASHED 2026-07-29 (rode along with the DMA race fix above); NOT yet verified on hardware**: data frames now carry a 4-byte source timestamp (`xTaskGetTickCount`, ms) and a CRC16-CCITT trailer instead of CRC8 XOR. Frame overhead 7 → 12 B (`SUBSCRIBE_STREAM_FRAME_OVERHEAD`). CSV columns are now `t_src_ms, t_host_s, seq, ...`. Host `decode_schema` now REFUSES a schema echoing a range that was not requested — closes the inbound-CRC8 hole where a transposed address byte could log the wrong variable under the right column name. 472 tests green + gcc harness. `Code=81468`, 0 errors. Flashed 2026-07-29 as part of the `Code=81484` image; the drone now runs v2 and `stream_log` should decode correctly, but **no stream has been run against v2 firmware yet** — verify before trusting a log.

**Rejected with evidence**: float16/int16 width reduction. Measured `mrac_state.pitch.Theta[2]` ≈ 8.4e-14 (float16 underflows to 0) and per-sample steps ~2e-5 relative (below float16's ~5e-4 resolution). Memory `project_stream_frame_budget`.

**Not done, deliberately**: raising UART5 baud (42 sites / 18 files incl. the flight dashboard — its own change); delta+keyframes (hold until bandwidth actually binds); downsampling (decide from a flight log, not bench data).

**Open question — RESOLVED**: no power-down needed. `rebuild_and_flash` neutralises `<pMon>` and was validated with the drone powered and streaming.

**Next action (streaming only — the session's live Next action is in the Dashboard Garbage-Telemetry block above)**: to log, edit `ground_station/livewatch/log_frames.md` then
`python -m ground_station.livewatch.stream_log --seconds 30 --out logs/run.csv`.
Note the 80 Hz command previously planned here would be REFUSED (4300 B/s vs the 2304 the firmware allows) — 20 Hz is the working figure on UART5.

**Uncommitted**: everything above. Nothing committed this session.

**Optimizations recommended, none implemented** (ranked, user asked what real streaming protocols do):
1. **Source timestamp in the frame (4 B)** — `t_s` in the CSV is currently *host arrival time*, smeared by USB/OS jitter. Wrong for system identification. Do this first.
2. **float16 / int16-with-scale per range** — 2× bandwidth, stateless, no loss risk. MAVLink-style.
3. **CRC-16-CCITT instead of CRC-8 XOR** — XOR misses byte transpositions; corrupt frames can land in the dataset looking plausible.
4. **Delta + keyframes** — big win, but stateful and dangerous on a lossy link. Hold until the bandwidth wall is actually hit.

**Hardware facts measured this session**: UART5 is **~101% saturated** (11677 B/s of an 11520 B/s cap). Frame rates AFTER the 2026-07-29 DMA race fix are 0x01≈65 Hz, 0x06≈65 Hz, 0x02≈16.3 Hz — the older 53/50/12 Hz figures were measured while ~97 % of Frame B was being corrupted and retransmitted, so they understate the real cadence. Not the 74% recorded before the `usart3_send()` busy-wait fix. Hence `SUBSCRIBE_BUDGET_PCT_UART5 = 20`. **USART3 is physically DISCONNECTED** — the operator cut the wire; COM3 silence is hardware, not firmware. Replacement BLE module (921600, +4 dBm) arrives ~2026-07-31 and is a drop-in for `--transport usart3`.

**Gotcha**: `SymbolResolver` does NOT bounds-check array indices — `Theta[63]` resolves happily although `MAX_NUM_BASIS` is 6 (`API/mrac.h:85`, NUM_BASIS 4 + 2 control terms). Confirm array lengths from the header.
