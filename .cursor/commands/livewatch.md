# Livewatch — read live firmware variables

Read any firmware variable off the **running** drone by name, over the wireless SWD probe.
No firmware change, no reflash. Use this instead of guessing what a value is at runtime.

Full contract: `.cursor/rules/hardware-safety.mdc` (always-on) and
`.claude/skills/livewatch/SKILL.md`.

## Safety

Permitted because `livewatch` **has no write path** — attach mode, no `write_memory`/`halt`/
`reset` anywhere in `reader.py`. It cannot arm, spin a motor, or halt the core.

**Still forbidden:** raw `pyocd`/`openocd`/`JLink`, `ground_station.flashtool`, any target
write, and editing `reader.py`'s connection options.

## 1. Verify first — not optional

```bash
python -m ground_station.livewatch verify
```

Reads resolve names to addresses via `OBJ/JX_FLY.axf`. A stale ELF returns **plausible-looking
garbage, not an error**. On `STALE ELF`: stop, report nothing, tell the operator to rebuild
(uVision GUI) or reflash.

## 2. Find the symbol (offline, no probe needed)

```bash
python -m ground_station.livewatch names --filter ekf
python -m ground_station.livewatch fields s_ekf
```

## 3. Read it

```bash
python -m ground_station.livewatch read s_ekf.x[3] Ctrler.locxPID.FB DroneStatus.ARM_Status
```

Paths are DWARF paths: `s_ekf.x[3]`, `mrac_state.roll.What[0]`. `group:<name>` expands from
`registry.yaml`.

## 4. Log a set to CSV (only if asked)

```bash
python -m ground_station.livewatch budget of_drift    # check the rate is achievable first
python -m ground_station.livewatch log of_drift --secs 60
```

Writes a unique CSV + `.meta.json` with resolved addresses and an ELF fingerprint. Refuses
rather than silently under-logging; `--clamp` accepts the measured ceiling.

## Rules of engagement

- **One process at a time** holds the probe. If Keil is debugging or the operator is streaming,
  your read fails — report it, do not loop.
- Prefer one-shot `read`. `watch`/`log` hold the interface for their whole duration.
- Retry `TransferError` with **exponential** backoff; the errors arrive in clusters.
- Cost is per-region AND per-byte — neighbouring struct fields coalesce and are much cheaper
  than scattered ones. Check `budget` before promising a sample rate.
- Report the value you actually read. Never infer one you could have measured.
