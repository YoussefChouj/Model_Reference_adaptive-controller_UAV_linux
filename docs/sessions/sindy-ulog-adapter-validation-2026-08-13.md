---
title: "prior-13b validation — fetched first real PX4 .ulg, found adapter bug"
date: 2026-08-13
type: validation-finding
status: paused
session: shell, no spec
related: [.agent_contracts/sindy-pipeline/SPEC.md, docs/authoritative-sources.md]
tags: [sindy, px4, ulog, adapter-bug, validation, prior-13b]
---

# Validation attempt — fetched real PX4 `.ulg`, adapter fails on modern schema

**Goal**: download a real PX4 `.ulg` and run `sim/sindy/adapters/ulog.py` end-to-end to validate the SINDy pipeline against real flight data.

**Outcome**: half-success. Got a real `.ulg` (1.76 MB, from UAV-SEAD HuggingFace mirror). Adapter loads the file and finds the topics, but the field-extraction path is broken against modern PX4 schemas.

## What worked

- **UAV-SEAD HuggingFace mirror** is the cleanest public dataset source. No bot protection, no S3-signed-URL gating. Direct LFS download of:
  - `https://huggingface.co/datasets/aykutkabaoglu/uav-flight-anomaly-dataset/resolve/main/ulg_files/log_135_2022-6-15-11-24-32.ulg`
  - 1396 logs total, 52 hours, organised by date folder. cc-by-4.0.
- `pyulog` (1.2.4) parses the file cleanly. 28 topics including all the ones the adapter expects.
- `logs.px4.io` is gated: anonymous `curl` to `https://cdn.logs.px4.io/<uuid>.ulg` returns 403 (CloudFront/S3 signed-cookie). The official download API is `https://review.px4.io/download?log=<id>` which 302s to the gated CDN. The `flight_review/download_logs.py` script handles this internally with a 6s rate limit. `firecrawl interact` can find the URL but cannot download past the gate.

## What broke

`sim/sindy/adapters/ulog.py::_get_topic_array` matches field names against hard-coded hints. Modern PX4 field names don't match the hints.

| Topic | Adapter expects | PX4 actually has | Match? |
|---|---|---|---|
| `vehicle_angular_velocity` | `xyz[0]`, `xyz[1]`, `xyz[2]` | `xyz[0]`, `xyz[1]`, `xyz[2]` | **Mismatch** — hints are `["[roll", "[pitch", "[yaw", "roll", "pitch", "yaw"]`, which do substring-match against the actual field names like `xyz[0]`. None match. |
| `vehicle_rates_setpoint` | `roll`, `pitch`, `yaw` | `roll`, `pitch`, `yaw` | **Mismatch** — hints are `["roll_rate", "pitch_rate", "yaw_rate"]`, no match. |
| `vehicle_attitude` | `q[0..3]` | `q[0]`, `q[1]`, `q[2]`, `q[3]` | **Probably broken** too — same hint pattern. |

The adapter docstring says "extracts the best available signals" but the implementation only matches one field-name schema.

### Evidence

```
$ .venv/bin/python -c "from sim.sindy.adapters.ulog import load_ulog; ds = load_ulog('raw/px4_logs/uav_sead_smallest.ulg', axis='roll')"
UserWarning: ulog raw/px4_logs/uav_sead_smallest.ulg has no vehicle_angular_velocity or vehicle_rates_setpoint topics
FAILED to load
```

But `pyulog` says the topics are present:
```
=== vehicle_angular_velocity ===
  fields: ['timestamp', 'timestamp_sample', 'xyz[0]', 'xyz[1]', 'xyz[2]']
  n samples: 1915
=== vehicle_rates_setpoint ===
  fields: ['timestamp', 'roll', 'pitch', 'yaw', 'thrust_body[0]', 'thrust_body[1]', 'thrust_body[2]']
```

## Recommended fix (not applied — for spec/scope decision)

Refactor `_get_topic_array` to:

1. Try known field-name patterns in order of preference:
   - `[roll/pitch/yaw]` (PX4 ≥ 1.10 rate_setpoint, `vehicle_rates_setpoint`)
   - `xyz[0..2]` (PX4 ≥ 1.12 `vehicle_angular_velocity`)
   - `roll/pitch/yaw` (older PX4 rate_setpoint)
2. Use **exact** field-name matching, not substring matching.
3. Return `None` only if no axis triplet is found.

The `axis_map` lookup at `load_ulog:96` (rate_idx, sp_idx) already encodes the [0,1,2] → roll/pitch/yaw convention, so the fix is contained to `_get_topic_array`.

## Tests to add with the fix

The adapter has **zero tests** (`sim/tests/test_sindy_*.py` covers loader + preprocessor only). The fix should add:

- `test_sindy_ulog.py::test_loads_modern_px4_schema` — synthetic ulog with `vehicle_angular_velocity.xyz[0..2]`
- `test_sindy_ulog.py::test_loads_old_px4_schema` — synthetic ulog with `vehicle_angular_velocity.[roll/pitch/yaw]` (legacy)
- `test_sindy_ulog.py::test_extracts_rate_setpoint` — setpoint field shape
- `test_sindy_ulog.py::test_missing_topic_returns_none` — graceful degradation
- `test_sindy_ulog.py::test_axis_map_is_roll_pitch_yaw` — axis mapping correctness

## Cache snapshot

- `.firecrawl/flight_review_download_logs.py` — official `download_logs.py` (346 lines, has rate-limit logic and `dbinfo` API URL)
- `.firecrawl/qav250-cdn-url.md` — confirmed CDN URL pattern, gates on session cookie
- `.firecrawl/uav-sead-hf.md` — HF dataset card, 417 lines
- `raw/px4_logs/uav_sead_smallest.ulg` — 1.76 MB, the file that triggered the bug

## Following work

- **`prior-13b` is blocked on this adapter bug.** The SINDy fitter, preprocessor, and prior_generator all work on synthetic data. The integration leg — "load real PX4, fit SINDy, extract prior" — does not.
- Recommended action: write a spec for `sindy-adapter-px4-schema-modernisation`, dispatch `uav-implementer` to fix + test, then resume `prior-13b`. Estimated scope: ~80 LOC + 5 tests.
- Alternative: park `prior-13b` and focus on other block-lifted specs (07, 09, 12) until the validation question matters again.