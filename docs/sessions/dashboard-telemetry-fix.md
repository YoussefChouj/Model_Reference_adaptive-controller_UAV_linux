# Dashboard garbage-telemetry / DMA race session (2026-07-29)

> Moved verbatim out of CLAUDE.md on 2026-08-09 to cut per-turn
> context churn. CLAUDE.md keeps a compact index pointing here.

### Dashboard Garbage-Telemetry Session (2026-07-29) — fix verified on the drone; commit decision still open

**Root cause (proved on the wire, NOT the flexible frame)**: `Send_Groundstation_Telemetry_UART4()` wrote the shared DMA buffer starting at `TASK/send_data.c:483` but waited for the previous DMA1_Stream7 transfer to drain ~586 lines later at old line 1069. Frame A (48 B, 4.2 ms) and the A+C burst (102 B, 8.9 ms) drain inside the ~18 ms tick and were never hurt. **Frame B is 305 B = 26.5 ms** — still in flight when the next tick rebuilt the buffer under it, so the wire got B's head + the new frame's bytes, then the new frame again in full.

**Fix**: moved the drain-wait ABOVE the first buffer write in `TASK/send_data.c` (now right after the local decls, before `Buf_Telemetry_UART4[0] = 0xAA`). Pure reordering — the identical wait already existed later, so per-cycle blocking and the EKF cadence are unchanged.

**Measured before → after** (3 s raw captures, scratchpad `frame_census.py` / `frame_headers.py` / `analyze_raw.py` / `align_check.py`):

| | before | after |
|---|---|---|
| Frame B CRC valid | 1/34 | **49/49** |
| Frame B on-wire size | 407 B (declared 305) — splice of +102 = A+C burst | **305 B exact** |
| Frame A CRC | 153/156 | **195/195** |
| Frame C CRC | 155/155 | **194/194** |
| alignment anomalies | 54 | **0** |
| rates | A 54 / C 50 / B 11.8 Hz | **A 65 / C 65 / B 16.3 Hz** |

PID block now decodes to real values (`0.7787, -0, -11.95, -1.118, 0, 12.89`) at offset +128 → the **4-MRAC-axis layout is correct**; the "3 axes" comment in `_unpack_frame_b` is stale doc, not a bug.

**FLASHED 2026-07-29** via `python -m ground_station.flashtool.rebuild_and_flash --yes`: `Code=81484`, 0 errors, ARM_Status=0 verified, succeeded attempt 1, `OBJ/JX_FLY.axf` now matches the running image. **This flash also shipped protocol v2** (stream source timestamps + CRC16) since it was in the tree — host and firmware are now BOTH v2, but v2 streaming is newly flashed and UNVERIFIED on hardware.

**Host-side fixes (same session, 487 tests green)**:
- `ground_station/gui/dashboard.py` `_sync_telemetry_from_bridge_if_local` — drops None-valued keys. The bridge nulls stale frames by design; consumers read via `k in a` / `a.get(k, 0.0)`, which raise `TypeError` on present-but-None and aborted the rest of `_frame()`, freezing every panel drawn after the raise.
- `ground_station/comm/serial_bridge.py` `get_telemetry_snapshot` — per-frame staleness windows `STALE_A_S=0.5` / `STALE_B_S=1.5` (old single 0.5 s sat just above Frame B's real 0.42 s worst gap); return type corrected to `Optional[float]`.
- `ground_station/gui/tests/test_stale_telemetry_none.py` — new, 4 regression tests.
- `ground_station/comm/test_frame_a_v13_contract.py` — was genuinely failing; asserted through the staleness guard after a 0.5 s sleep. Now reads `_last_telemetry_*` directly. That dir is NOT in `pytest.ini` testpaths, so it never ran in the normal suite.

**Environment**: `.venv` was EMPTY (that was the original "python.exe not recognized"). Rebuilt with **Python 3.13** — 3.11 cannot satisfy `requirements.txt` (`scipy==1.18.0` needs ≥3.12). The `-e git+...llmwiki` line has no checkout and nothing imports it; skip it. Memory `project_venv_python_version`.

**Open question posed to the user, UNANSWERED**: "Want me to commit the race fix separately so it has its own clean history?" Nothing is committed — the firmware fix, both host fixes and the new tests sit in the working tree alongside the pre-existing streaming-session changes.

**Next action**: await that answer. If yes: commit `TASK/send_data.c` alone with the before/after CRC table in the message, then the host fixes + tests as a second commit.

**Still open, not urgent**: link remains ~101 % saturated (11677 B/s of 11520) — all useful now, but no headroom for a UART5 stream; `Uart5_Subscribe_TxSend` (`BSP/usart5.c:144`) busy-waits on DMA1_Stream7 with NO non-blocking guard, unlike the USART3 path in `API/subscribe.c:700-707` — will stall Send_Task once a UART5 stream runs; `serial_bridge._rx_loop` (~line 1341) does not skip payloads of unknown frame types (0x07/0x08/0x09-0x0C/0x7F), so it rescans them byte-by-byte and can false-sync — latent until streaming resumes.
