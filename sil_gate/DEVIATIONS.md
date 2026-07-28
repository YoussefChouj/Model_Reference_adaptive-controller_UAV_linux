# SIL Gate — Deviation Register

Places where the firmware intentionally differs from `sim/`. When the
gate reports a mismatch, this file is the first place to check: if the
mismatch is here, it's expected; if it isn't, it's a defect.

| # | Module | Firmware behaviour | Sim behaviour | Where |
|---|--------|--------------------|---------------|-------|
| 1 | MRAC | `What_lower_limit = 0` (never set in `MRAC_Init`) — weights live in `[0, What_limit]`, MRAC cannot produce negative `u_ad` | Sim mirrors: `What_lower_limit` defaults to 0 | `API/mrac.h` + `sim/adaptive_law.py` (mirrored deliberately) |
| 2 | MRAC | `e_deadzone = 0.05 rad/s` — adaptive law freezes below this tracking error | Sim mirrors | `API/mrac.h` `MRAC_AxisConfig_t.e_deadzone` + `sim/adaptive_law.py` |
| 3 | EKF | `k_last` is **overwritten** by every update call — after `UpdateOf` it holds K[:,0]; after `UpdateZRate` it holds K[:,2] | sim/ekf.py caches only `self._K_of = K[0:3, 0]` and never touches it again | `API/ekf.c` lines 214-216, 302-304. Gate's `run_sim` (`sil_gate/runner.py`) mirrors the overwrite to compare like-for-like |
| 4 | EKF | Default `dt` is unspecified — `Ekf9_Predict`'s last argument is the only dt source | sim/ekf.py `Ekf9State` carries a per-instance `dt` default of 0.001 s | `API/ekf.h` (`Ekf9_Predict(e, ..., dt)`) vs `sim/ekf.py` (`predict(..., dt=None)`) |
| 5 | EKF | `Ekf9_UpdateAccXY` is misnamed — H selects `v_body[0..1]` (velocity), not acceleration. The only valid call is `(0, 0)` (ZUPT) | `update_acc_xy` documented identically. Sim tests use `(0, 0)` only | `API/ekf.h:60-61` warning comment. SIL gate's runner always calls with `(0, 0)` |

## How to read this register

When the gate reports a mismatch:

1. Check whether the failing signal is on this list. If yes:
   - Confirm the deviation is still in force (sometimes firmware is
     "fixed" without telling sim — drift in the other direction is
     worse than drift in the documented one).
   - The gate is doing the wrong thing if it fails the trajectory on
     a deviation. Adjust either the deviation's documentation or the
     gate's tolerance.
2. If the failing signal is NOT on this list, it is a finding. Either:
   - The firmware has a defect the gate caught (the happy case), or
   - The sim has a defect the firmware caught (also valid; spec says
     conclude after investigation that the model was wrong and the
     firmware right is a legitimate outcome).

A new entry here is added only when an investigation concludes the
mismatch is intentional. Speculative entries are not allowed.

## Notes on intentional absences

These are NOT deviations — the gate does not compare them, by design:

- **`s_Po[81]`, `s_AP[81]`** file-scope scratch in `API/ekf.c`. These
  are non-re-entrant by design (single EKF instance, called only from
  Send_Task whose stack is 500 words / 2 kB). Sim has no equivalent
  storage constraint. The gate cannot compare storage layouts and
  doesn't try to.
- **`active` flag**, **working buffers `S[9]`, `K[27]`** in
  `Ekf9_t`. The gate checks the Init defaults via
  `test_ekf_init_defaults_match_sim` but not the post-update values of
  the working buffers — they are transient, not state.