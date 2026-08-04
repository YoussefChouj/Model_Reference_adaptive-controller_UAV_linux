# Verify protocol v2 against the running firmware

Type: task
Status: open

## Question

Nothing to decide — a verification that must happen before anything is built on top of the
subscription path, which is now the whole destination.

Protocol v2 shipped in the 2026-07-29 flash (`Code=81484`) as a passenger on the DMA race
fix. Data frames now carry a 4-byte source timestamp (`xTaskGetTickCount`, ms) and a
CRC16-CCITT trailer instead of the CRC8 XOR; frame overhead went 7 -> 12 B
(`SUBSCRIBE_STREAM_FRAME_OVERHEAD`); CSV columns became `t_src_ms, t_host_s, seq, ...`;
and host `decode_schema` now refuses a schema echoing a range that was not requested.

**No stream has ever been run against v2 firmware.** Host and firmware are both v2 in
source and 472 tests plus the gcc harness are green, but the pairing is unexercised on the
drone. That matters more now than it did when it was noted, because the redrawn map makes
this path carry all telemetry: refactor on top of an unverified protocol and a failure
cannot be attributed between a v2 bug and a migration bug.

What to produce:

- A stream run against the current flashed image, decoded by the current host, with
  **0 dropped and 0 malformed** — the same bar the v1 multi-slot run cleared on 2026-07-29
  (3 slots at 20/10/5 Hz over 30 s).
- Confirmation that `t_src_ms` advances monotonically and at the expected cadence. This is
  the whole point of v2 — `t_host_s` is arrival time smeared by USB and OS jitter, and is
  wrong for system identification.
- Confirmation that CRC16-CCITT actually rejects a corrupted frame rather than silently
  passing it, and that the `decode_schema` range-echo refusal fires when it should.
- A note on whether the measured overhead matches the declared 12 B.

How to run it: edit `ground_station/livewatch/log_frames.md` (a Markdown table — **editing
it needs no rebuild**) then
`python -m ground_station.livewatch.stream_log --seconds 30 --out logs/run.csv`.

Constraints: 20 Hz is the working figure on UART5 — the firmware permits 2304 B/s but only
~1600 B/s arrives intact, and 2055 B/s dropped 14% on every slot. Do not exceed that here;
this ticket is verifying the protocol, not probing the ceiling.
`SymbolResolver` does **not** bounds-check array indices — `Theta[63]` resolves happily
although `MAX_NUM_BASIS` is 6 — so confirm array lengths from `API/mrac.h`, not by guessing.

**Requires an explicit operator go-ahead in chat before any target interaction.** No flash
should be needed; the image already runs v2.
