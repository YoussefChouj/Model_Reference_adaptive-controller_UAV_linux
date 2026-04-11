# VOFA Context Switch Audit (A/B Buttons)

Date: 2026-04-10
Scope: Ground-station VOFA launcher behavior in `ground_station/gui/dashboard.py`

## Why this audit exists

User-reported failures persist:
- Editing variable names in Frame B leaks into Frame A.
- Opening A/B is not deterministic from user perspective.
- Sometimes opening one appears to reopen or conflict with the other.

This document is intended as a handoff package for another agent to perform a root-fix implementation.

## Current launcher wiring (verified)

- Frame A button callback:
  - `_open_plot("presets/vofa/full.tabviews.json", stream="a")`
- Frame B button callback:
  - `_open_plot("presets/vofa/mrac_errors.tabviews.json", stream="b")`

Relevant code entry points:
- `_infer_stream_from_context_cfg` (line ~1448)
- `_sync_system_context_to_stream_cache` (line ~1486)
- `_stage_stream_cache_to_system_context` (line ~1506)
- `_ensure_vofa_stream_context` (line ~1523)
- `_prepare_vofa_runtime` (line ~1549)
- `_apply_vofa_channel_labels` (line ~1733)
- `_terminate_vofa_instances` (line ~1799)
- `_open_plot` (line ~1831)

Config state:
- `vofa_manual_mode: 1`
- `vofa_port_a: 1347`
- `vofa_port_b: 1348`

## Runtime evidence snapshot

Collected from:
- System context: `%LOCALAPPDATA%/vofa+/100/context`
- Stream caches:
  - `ground_station/.vofa_runtime/a/localappdata/vofa+/100/context`
  - `ground_station/.vofa_runtime/b/localappdata/vofa+/100/context`

Observed values:

- SYSTEM
  - `PORT=1348`
  - `TABS=B MRAC Tracking|B Pitch Theta`
  - `NAMES_HEAD=mrac_pitch_theta_0,mrac_pitch_theta_1,...`

- CACHE_A
  - `PORT=1347`
  - `TABS=A MRAC Errors|A MRAC Adaptive|A Status`
  - `NAMES_HEAD=mrac_pitch_theta_0,mrac_pitch_theta_1,...`  <-- B-style names inside A cache

- CACHE_B
  - `PORT=1348`
  - `TABS=B MRAC Tracking|B Pitch Theta`
  - `NAMES_HEAD=mrac_pitch_theta_0,mrac_pitch_theta_1,...`

Interpretation:
- A/B tab layouts are separated.
- A/B UDP ports are separated.
- Channel-name state (`settings_ctx`) is not separated correctly.

## Findings (ordered by severity)

1. Stream cache initialization is cross-contaminating names.
- In `_ensure_vofa_stream_context`, when target stream config does not exist, it copies system config:
  - `src_cfg = self._get_vofa_context_config_path()` then `shutil.copy2(src_cfg, target_cfg)`
- If system currently reflects B, newly created A cache inherits B channel names.
- This is a direct, deterministic contamination path.

2. Stream inference uses only UDP local port, not channel schema identity.
- `_infer_stream_from_context_cfg` determines stream from `udp.local_port` only.
- If A cache already has B names but port 1347, function still classifies it as A and syncs corrupted config into A cache.
- This locks in contamination.

3. Channel names live in global `settings_ctx`, not in tabviews.
- Tabviews can be A while names remain B.
- This matches screenshots where A tabs appear with B-style names.

4. Manual mode still mutates stream config ports/protocol each launch.
- `_prepare_vofa_runtime` rewrites UDP/protocol in config on every open.
- This is expected for ports but means manual mode is not fully read-only.

5. "Opening one opens another" likely race/process-state related, not callback wiring.
- Only one `subprocess.Popen([vofa], ...)` exists in `_open_plot`.
- Potential causes:
  - repeated rapid clicks before UI lock/debounce,
  - process shutdown/start race,
  - VOFA instance behavior during taskkill/restart window.

## Root-cause summary

Primary root cause:
- Stream-specific cache seeding from mutable system config (`vofa+.config.json`) causes stream identity drift in `settings_ctx`.

Secondary design gap:
- No stream-specific source of truth for channel names.
- Stream identity detection does not validate schema compatibility.

## Guidance for root-fix implementation

### Design target

Guarantee independent, persistent state per stream for three things:
1. UDP port binding
2. Tabs/layout
3. Channel names

### Required implementation changes

1. Introduce immutable per-stream baseline configs.
- Add two baseline files under project control, e.g.:
  - `ground_station/presets/vofa/baseline_a.config.json`
  - `ground_station/presets/vofa/baseline_b.config.json`
- Baseline A `settings_ctx` must use A names.
- Baseline B `settings_ctx` must use B names.

2. Change cache bootstrap logic.
- In `_ensure_vofa_stream_context`:
  - do NOT seed `target_cfg` from system config.
  - seed `target_cfg` from stream baseline.
  - seed `target_tabviews` from stream workspace preset.

3. Separate first-run initialization from regular switching.
- First-run only: create cache from baseline/preset.
- Regular switch: sync closed system context back to inferred active cache, then stage target cache.

4. Improve stream inference.
- Keep port check, but add schema fingerprint check:
  - A fingerprint: first names expected from frame A (`mrac_pitch_e`, `mrac_pitch_u_ad`, ...)
  - B fingerprint: expected theta fields (`mrac_pitch_theta_0`, ...)
- If port and schema disagree, treat context as contaminated and recover from baseline for that stream.

5. Add contamination guard.
- Before staging target cache to system:
  - verify target stream port and schema.
  - if invalid, auto-repair from baseline + preserve tabviews if possible.

6. Add launch debouncing/lock.
- Disable both A/B buttons during switch sequence.
- Re-enable after process spawn delay.
- Prevent accidental double-open race.

7. Add deterministic launch telemetry (for debugging).
- Append to `ground_station/.vofa_runtime/launch_audit.log` per click:
  - timestamp, requested stream, inferred active stream,
  - system port/schema before sync,
  - target cache port/schema before stage,
  - process count before/after launch.

## Verification plan (must-pass)

1. Clean bootstrap test
- Delete `ground_station/.vofa_runtime`.
- Open B first, rename channels, close.
- Open A first time.
- Expected: A names are A baseline names, not B names.

2. Alternating persistence test
- A: rename a few A channels, close.
- B: rename a few B channels, close.
- Reopen A then B.
- Expected: each stream keeps its own names and tabs.

3. Port correctness test
- A always launches with local port 1347.
- B always launches with local port 1348.

4. Race test
- Rapidly click A/B buttons multiple times.
- Expected: no duplicate opens and no cross-contamination.

5. Recovery test
- Manually corrupt A cache names with B schema.
- Open A.
- Expected: contamination guard restores A schema while keeping A tabs if possible.

## Minimal task list for next agent

1. Add baseline A/B config assets with correct `settings_ctx`.
2. Refactor `_ensure_vofa_stream_context` to use baselines only.
3. Implement schema fingerprint + contamination guard.
4. Add button lock/debounce around `_open_plot`.
5. Add launch audit logging.
6. Run verification plan above and capture results.

## Notes

- This audit intentionally does not prescribe UI/tab aesthetic details.
- The core defect is state ownership and cache seeding strategy, not button callback wiring.
