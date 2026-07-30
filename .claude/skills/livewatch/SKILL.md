---
name: livewatch
description: >
  Read or log ANY firmware variable from the running drone by name, live, over the
  wireless SWD probe — no firmware change and no reflash needed. Use when the user
  asks what a variable is doing on the target, wants to check firmware state against
  the code, asks to log/stream/record variables to CSV, mentions "live read",
  "what is X right now", "watch X", "log X at N Hz", or when you are about to reason
  about runtime behaviour you could simply measure instead.
---

# livewatch — live firmware variable access

Reads RAM off the running STM32F407 via pyOCD in **attach mode**. Resolves any symbol
from DWARF in `OBJ/JX_FLY.axf`, so **any** global, struct field, or array element is
readable by name with zero firmware changes.

## SAFETY — read the constraint before the commands

The drone is **disarmed on the bench with props installed**.

`livewatch` is safe because **it has no write path**: `reader.py` uses
`connect_mode="attach"`, `resume_on_disconnect=False`, and contains no `write_memory`,
`halt`, or `reset` call. It cannot arm, spin a motor, halt the core, or change any
state. Reading RAM cannot move the ARM flag.

**Do not** weaken that: never add a write path, never change the connection options,
never call raw `pyocd` yourself, and never invoke `ground_station.flashtool` (it writes
flash and is the operator's tool). Any target *write* or physical bench action belongs
to the human operator.

## ALWAYS run verify first

```bash
python -m ground_station.livewatch verify
```

Every read turns a NAME into an ADDRESS using the ELF. **If the ELF is not the flashed
build, you get plausible-looking garbage rather than an error** — a float is a float
whatever it points at. `verify` compares sampled flash bytes against the ELF and exits
non-zero on mismatch.

If it says `STALE ELF`: **stop**. Report nothing you read. Rebuilding and reflashing is the
`stream-log` skill's section 2 — headless `UV4` does work, but only with the target powered
down, and the power sequencing there is not optional.

## Commands

Offline (no hardware, no probe contention — use freely):

```bash
python -m ground_station.livewatch names --filter ekf   # find symbols
python -m ground_station.livewatch fields s_ekf         # struct members / array elems
python -m ground_station.livewatch groups                # registry.yaml groups
python -m ground_station.livewatch manifests             # logging manifests
python -m ground_station.livewatch budget of_drift       # feasible sample rate
```

Live (needs the probe):

```bash
python -m ground_station.livewatch read s_ekf.x[3] DroneStatus.ARM_Status
python -m ground_station.livewatch watch group:ekf --hz 20 --secs 30
python -m ground_station.livewatch log of_drift --secs 60
python -m ground_station.livewatch log --vars group:ekf s_of_bias_x --hz 50 --name probe
```

Name syntax is a DWARF path: `s_ekf.x[3]`, `mrac_state.roll.What[0]`, `Ctrler.locxPID.FB`.
`group:<name>` expands from `registry.yaml`.

## Logging to CSV

`log` writes a uniquely named CSV plus a `.meta.json` recording resolved addresses and an
**ELF sha256 fingerprint** — an address-resolved log is meaningless against the wrong build,
so never hand-edit or rename away that sidecar.

Rate feasibility is **measured, not assumed**. `log` calibrates against the live target and
**refuses** rather than silently producing a CSV that logs slower than its filename claims.
Pass `--clamp` to log at the ceiling instead. Add manifests to `manifests.yaml` freely — a
manifest is just a list of names, so it costs nothing and needs no reflash.

## Performance model

The probe is **bandwidth**-limited, not latency-limited: `t_ms ≈ 1.9·regions + 0.0297·bytes`
(~33 KB/s, ~1.9 ms per transaction). Adjacent struct fields coalesce into one read, so
**a few neighbouring fields are far cheaper than the same count scattered across the map.**
Rough ceilings: 8 vars ≈ 320 Hz, 16 ≈ 250 Hz, 32 ≈ 170 Hz, 64 ≈ 100 Hz. Use `budget` to check
before promising a rate.

## Gotchas

- **One process at a time** holds the CMSIS-DAP interface. If Keil has a debug session open,
  or a `watch`/`log` is running, reads fail. Report it; do not retry in a loop.
- The probe throws `TransferError` in **clusters**. Retry with exponential backoff — a fixed
  short delay burns every attempt inside one bad patch.
- Prefer one-shot `read` over `watch`/`log`, which hold the interface for their full duration.
- `system_monitor.USART2_task_cnt` is **useless for rate measurement** — incremented in both
  the USART2 RX ISR and `Send_Task`, and zeroed every period by `systemmonitor_task.c`. The
  `*_fps` fields read as `1` and are not usable either.
- pyOCD's `read_memory_block8` degrades to byte-at-a-time `read8` for unaligned/sub-word
  symbols, and that path fails far more often on this probe. If you script raw reads, read the
  **enclosing aligned word with `read32`** and mask.

## Verify claims, don't assume them

When a firmware value looks wrong, check the caller's units, `dt`, and bias conventions before
touching any math — most such bugs are call-site bugs in numerically correct code. And a
filter whose output closely matches its own dominant input is a **degeneracy signature**, not
success: check `b_a` against raw `Acc_*_Real` directly; a ratio near 1.0 means passthrough
however good the RMSE looks.
