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
  `divider = round(80.4 / rate)`.
  Achieved rates land ~8 % under the request; `seq` is the ground truth.
- **Slots.** Four. A fifth `--group` is an error, not a queue.

### `--transport usart3` — the wire is fine, the HOST TOOL is broken

Superseded note, kept so it is not re-derived: this file used to say the USART3 wire was
physically cut and the transport was dead. **That is no longer true.** The 24RF radio was
retired and commit `05ae422` moved the downlink onto a BLE module at `USART3_BAUD 921600`
(`BSP/usart3.h:25`). The link works.

**But do not reach for `--transport usart3` expecting it to work.** Four defects, all
verified still present on 2026-08-09, would make it fail *silently* rather than loudly:

| # | Where | Defect |
| --- | --- | --- |
| 1 | `stream_log.py:391` | usart3 data port defaults to `COM3`; the dongle is **COM7** |
| 2 | `stream_log.py:114,116,289,291` | data port opened at hardcoded `115200` — decodes **garbage** against a 921600 link |
| 3 | `stream_log.py:264` | `usart3_baud=115200` is a function parameter with **no CLI flag** |
| 4 | `API/subscribe.c:531` | budget cap is `USART3_BAUD/10` = 92160 B/s, but the radio's **measured** ceiling is ~6.7 kB/s |

Defect 4 is the dangerous one: the firmware will happily *accept* a subscription an order
of magnitude beyond what the radio can carry, so the refusal you rely on (`0x7F`) will not
fire. The cap must be the measured air ceiling, not baud arithmetic.

Fix 1–3 before using this transport, and size any request against ~6.7 kB/s — not 92 kB/s.

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
3 build failed, 4 `uvoptx` not restored byte-exact, 5 target dark, 6 arm gate refused
(armed, no readable arm flag anywhere, or the two oracles disagreeing), 7 flash failed
after retries, 8 target did not come back up.
**Never work around a non-zero exit** — each one means a specific guard fired.
**Every refusal restores the flashed artifacts**, so a refused run never leaves a stale
ELF in `OBJ/` for the next run (or livewatch) to trust.

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
4. **Runs the two-oracle arm gate** (rebuilt 2026-08-09 — the old single unvoted SWD read
   reported ARMED for a demonstrably disarmed drone, and the same fault can report
   DisArmed for an armed one). **Telemetry is primary**: Frame A `status_arm`, packed by
   the firmware, so it depends on neither the ELF nor the probe. The SWD read is
   secondary, voted 9× requiring unanimity, and only counts if `elf_matches_target()`
   proves its ELF is the running image — otherwise it abstains, since a stale ELF would
   otherwise deadlock the pipeline (only flashing resyncs it). Disagreement ⇒ refuse.
   No arm flag anywhere ⇒ refuse. `--arm-port` picks the telemetry port; it must carry the
   `0xAA 0xBB` envelope, so USART3 does **not** qualify while it emits the bare JustFloat
   throughput ladder. **Do not weaken this gate** — it is the operator's sole safety limit
   for flashing, by explicit policy.
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

**But do not read that as "`rebuild_and_flash` is therefore clean."** Finding (d) — a
refusal path skipping the artifact restore — turned out to be present in
`rebuild_and_flash` too, found live 2026-08-09. Each refusal left the unflashed build in
`OBJ/`, so the *next* run snapshotted it as "the flashed artifacts" and resolved the arm
flag through a wrong address; refusals compounded, and a wrong address reads garbage
*reproducibly* (a unanimous 9/9 "armed" against 126 telemetry frames saying disarmed).
Fixed — every refusal now restores. Not importing a defective module is not the same as
not sharing its defect.

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
