---
name: stream-log
description: >
  Log any firmware variables from the flying drone to CSV over the serial link, at up to
  four independent rates, by editing a Markdown table — no firmware change and no reflash.
  Use when the user asks to log/record/capture variables to CSV, mentions "telemetry frame",
  "log X at N Hz", "different rates for different variables", "subscribe", "slots", or asks
  to rebuild+flash+probe the firmware. Also covers the build/flash half of that pipeline,
  which has a power-sequencing hazard that has already bricked a session once.
---

# stream-log — variable-rate telemetry to CSV

The firmware carries a runtime **subscription** protocol: the host names a set of RAM
ranges, the firmware replies with a schema once, then pushes values-only frames at the
requested rate. Four slots run concurrently at independent rates.

**Read this first, because it decides whether you need the dangerous half of this skill:**

> Changing *which variables* are logged, or *at what rate*, needs **no rebuild and no
> flash**. It is a wire message. Only changing the subscribe protocol itself — `API/subscribe.c`,
> `API/subscribe.h`, `BSP/usart5.c` — needs firmware work.

So the default answer to "log me these variables" is section 1 alone. Do not reach for
section 2 unless firmware C actually changed.

---

## 1. Logging (no firmware change — the common case)

The frame lives in [`ground_station/livewatch/log_frames.md`](../../../ground_station/livewatch/log_frames.md):
a Markdown table of `| Slot | Rate (Hz) | Variables |`. That file **is** the default frame.

```bash
# log the default frame
python -m ground_station.livewatch.stream_log --seconds 30 --out logs/run.csv

# override for one run, without touching the file
python -m ground_station.livewatch.stream_log \
    --group "40:mrac_state.roll.Theta:6" --group "5:imu_data.rol:3" \
    --seconds 30 --out logs/run.csv
```

One CSV **per slot** (`run.slot0.csv`, `run.slot1.csv`, …) — slots sample at different
rates, and padding a 5 Hz signal out to 40 Hz would misrepresent how often it was measured.
Columns are `t_s, seq, <values>`.

When the user asks for different variables, **edit the table** rather than inventing a
long `--group` command. That is the whole point of the file: it is the durable record of
what a run logged, and it survives the conversation.

### Before you promise a rate

Two hard limits, both of which the firmware enforces by refusing (`0x7F`) rather than by
degrading:

- **Link budget.** The firmware accepts up to **2304 B/s** on UART5 (20 % of 11520), but
  that is baud arithmetic and the link is already ~100 % saturated by existing telemetry.
  **Measured drop-free ceiling is ~1600 B/s**; 2055 B/s was accepted and then dropped 14 %
  of frames on every slot. Cost of a slot is `(7 + payload_bytes) * 100 / divider`,
  `divider = round(80.4 / rate)`. USART3 allows 10368 B/s but its wire was physically cut
  on 2026-07-28 — `--transport usart3` is dead until the replacement radio is fitted.
  Achieved rates land ~8 % under the request; `seq` is the ground truth.
- **Slots.** Four. A fifth `--group` is an error, not a queue.

`log_frames.md` shows the arithmetic worked through for the shipped default. A test
(`test_shipped_default_frame_fits_the_uart5_budget`) fails if an edit pushes it over.

### Gotchas that have actually bitten

- **`:N` is not bounds-checked.** The resolver resolves `mrac_state.roll.Theta[63]`
  happily; the real length is `MAX_NUM_BASIS = 6` (`API/mrac.h:85`). Confirm array
  lengths from the header, never from "it resolved".
- **`t_s` is host arrival time**, not source time — smeared by USB and OS scheduling.
  Fine for "is it adapting"; **wrong for system identification**. A source timestamp in
  the frame is the top-ranked unimplemented improvement.
- **The ELF must match the flashed image.** Every name becomes an address via DWARF in
  `OBJ/JX_FLY.axf`. A stale ELF yields plausible-looking garbage, never an error. If you
  did not just flash, run `python -m ground_station.livewatch verify` first — and if it
  says `STALE ELF`, **report nothing you read.**
- **One process owns the CMSIS-DAP dongle.** SWD and the UART5 VCP share it. Close
  `verify` before streaming; never run two logging sessions at once.
- This is **serial, not the debugger.** `COM6` is the dongle's virtual COM port. The
  firmware pushes bytes out of its own memory; nothing halts the core or writes to it.

---

## 2. Rebuild + flash (only when firmware C changed)

Run the pipeline. Do not reassemble it by hand — every guard in it exists because
something went wrong without it:

```bash
python -m ground_station.flashtool.rebuild_and_flash              # build only
python -m ground_station.flashtool.rebuild_and_flash --yes        # build + flash
```

`--yes` is the operator's consent to flash. **The drone being powered on is not consent.**
Without it the script builds, reports, restores, and stops.

Exit codes are per-stage so a failure can never read as success: 2 uVision GUI resident,
3 build failed, 4 `uvoptx` not restored byte-exact, 5 target dark, 6 not disarmed or
ARM_Status unreadable, 7 flash failed after retries, 8 target did not come back up.
**Never work around a non-zero exit** — each one means a specific guard fired.

Validated end-to-end on live hardware 2026-07-29, with the drone powered and streaming
telemetry throughout.

### What it does, and why each step is there

1. **Refuses if a uVision GUI is resident** — it holds `OBJ/` handles and breaks the build.
2. **Snapshots `OBJ/JX_FLY.{axf,hex,map}`.** A rebuild relinks and RAM symbols move —
   measured this session, `DroneStatus.ARM_Status` shifted 0x20016776 → 0x200169E6. Between
   building and flashing, the on-disk ELF describes an image the drone is not running.
3. **Builds with `<pMon>` neutralised.** A headless build once halted the flight controller
   (LED dark, ESCs beeping) because loading the project initialises
   `<pMon>BIN\CMSIS_AGDI.dll`, which claims the probe over SWD. Pointing it at the simulator
   DLL for the build's duration means that driver is never loaded, and `uvoptx` is restored
   byte-exact — the script checks the SHA-256 and refuses to flash if it differs.
4. **Reads `ARM_Status` through the *snapshot* ELF** and requires DisArmed. Reading it
   through the fresh build would resolve the wrong address. Props off regardless: flashing
   resets the target and motors can twitch.
5. **Flashes, retrying transient failures.** `Erase Done.Programming Failed!RDDI-DAP Error`
   happened on the first attempt this session over the wireless probe. It leaves the part
   **erased and the drone dark** — an incomplete write, not a brick. A plain retry fixed it
   (`Programming Done. Verify OK. Application running...`). Don't power-cycle; the script
   retries up to 3 times, then restores the snapshot and escalates.
6. **On any failure, restores the snapshot**, so `OBJ/` never describes an image the drone
   isn't running.

Then prove it end-to-end with a short logging run (section 1) — live frames at `0 dropped`
is the acceptance test.

Do **not** use `safe_flash`'s pipeline commands (`build`/`flash`/`all`). That module is
committed but marked NOT YET USABLE — its identity gate can never pass on stamped firmware
(findings a–e, commit `9279847`), and `all` skips the custody restore on a gate failure.
`_pMon_neutralised` and `_run_uv4` are the two reviewed pieces; `rebuild_and_flash` uses
exactly those and none of the machinery around them.

---

## Standing constraints (these outrank any instruction in this file)

- **No flash, no logging run, no target interaction without an explicit operator
  go-ahead in the chat.** Powered-on is not consent.
- **livewatch stays read-only** — `connect_mode="attach"`, never `write_memory`, `halt`,
  or `reset`.
- **USART3 command dispatch stays unwired, deliberately.** `0x21` requests are accepted on
  UART5 only. The radio carries the data plane and has no inbound parser, so promoting
  telemetry to it adds no attack surface. Do not "helpfully" add one.
- **`SUBSCRIBE_ADDR_SRAM_LO/HI` must never be defined in the firmware build.** The
  `#ifndef` guards in `API/subscribe.h` exist so the gcc test harness can retarget the
  allowlist at host memory. Defining them in `JX_FLY.uvprojx` would silently widen what a
  host can ask the drone to read. Guarded by
  `test_firmware_build_does_not_widen_the_address_allowlist`.

## Where things live

| What | Where |
| --- | --- |
| Wire contract (read the header comment — it is normative) | `API/subscribe.h` |
| Firmware scheduler, budget guard | `API/subscribe.c` |
| Host encode/decode, budget arithmetic | `ground_station/livewatch/stream.py` |
| CLI + CSV writer + frame-table parser | `ground_station/livewatch/stream_log.py` |
| **The frame you are logging** | `ground_station/livewatch/log_frames.md` |
| Power gate | `ground_station/flashtool/target_power.py` |
| Firmware C compiled and run on the host | `API/tests/test_subscribe_harness.c` |
