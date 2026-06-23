# SysID Results — canonical reference

Single source of truth for the identified inner-loop (rate) plant models and the
recommended MRAC reference-model bandwidths. Update this file whenever a new SysID
campaign supersedes the numbers below; keep the previous block under "History".

> Generated/maintained by hand from `ground_station/scripts/sysid_analysis.py` output
> (per-log `report.md` under `ground_station/analysis/`). Model structure:
> **`G(s) = K / (s·(1 + s/p))·e^(−sT)`** — rigid-body integrator + one lumped
> actuator/ESC/gyro-filter lag pole `p` + transport delay `T`. `K` and the mixer
> torque effectiveness are coupled, so `K` is a lumped input→output gain, **not** a
> physical inertia (ADR-0004).

---

## Current best estimates

| Axis | `ref_model_bw` (rad/s) | K | lag pole `p` (rad/s / Hz) | delay `T` (ms) | VAF | Source | Status |
|---|---|---|---|---|---|---|---|
| **Roll** | **44.1** | ~165 | 19.8 / 3.15 | 15 | ~99 % | multisine ×7, 2026-06-18 | ✅ validated, repeatable < 0.3 %; cross-checks chirp |
| **Pitch** | **44.1** | ~185 | 16–18 / ~2.6 | ~12 | ~98 % | multisine ×2 clean, 2026-06-18 | ✅ matches roll (symmetric quad); links flaky but 2 runs agree on 44.1 |
| **Yaw** | (set by loop gain) | **~37 (K/s)** | none (pure integrator) | ~0 | n/a (K/s) | multisine+chirp, 2026-06-18 | ✅ identified as pure integrator G≈37/s; rel-degree 1 |
| Z (alt) | — | — | — | — | — | — | ⬜ axis not wired (ADR-0004 #1) |

**Roll details (2026-06-18 multisine campaign — current best)**
- Excitation that produced the validated number: **multisine** (Schroeder, pre-emphasised),
  0.5–15 Hz, ~35 °/s, 33 s, ×7 valid runs (crest factor ≈ 3.45, classified correctly).
- `ref_model_bw ≈ 44.1 rad/s` (7.02 Hz) — closed-loop −3 dB bandwidth of x/r,
  spread **44.04–44.18 rad/s (< 0.3 %)** across 7 independent runs.
- Plant fit `G(s) = K/(s(1+s/p))·e^(−sT)`: K ≈ 165, p ≈ 19.8 rad/s (3.15 Hz), T ≈ 15 ms, VAF ≈ 98.7 %.
- Captured at a **stable 200 Hz** (6600 counts / 33 s every run) — confirms the Send_Task
  `vTaskDelay` pacing fix + multisine spectral pre-emphasis are live and effective.
- **Cross-validation:** agrees with the 06-17 chirp model (39.3 rad/s, p 2.4 Hz, T 12 ms) to
  within ~12 %; the higher pole/bandwidth is the expected result of flattened HF coherence
  letting the fit reach further up in frequency. Two excitation families → same plant.
- ⚠️ Battery not logged this campaign (`id.vbat = 0`): the 06-18 firmware flown predates the
  `Get_Voltage()`-in-`SystemMonitor_Task` fix (it is in source, `USER/main.c:109`, but not in
  the flashed build). Reflash before the next campaign to capture the voltage operating point.

**Pitch details (2026-06-18)**
- Two clean multisine runs (sysid_pitch_1781788765 link 100 %, 1781790819 link 93 %) both give
  `ref_model_bw = 44.1 rad/s`, K ≈ 185, pole ≈ 2.6 Hz, delay ≈ 12 ms, VAF ≈ 98 % — essentially
  identical to roll, as expected for a near-symmetric quad.
- Run-to-run `ref_bw` looser than roll (39–49 rad/s across all runs) because (a) most runs had
  telemetry frame drops and (b) one motor-arm side carries a guard → mild fore/aft asymmetry the
  multisine averages over. The MRAC online adaptation absorbs that asymmetry.
- Many pitch attempts were drop-wrecked; the new analyzer link-quality gate flags them (BAD/WARN).

**Yaw details (2026-06-18) — identified as a PURE INTEGRATOR**
- `G_yaw(s) ≈ K/s` with **K ≈ 37** (no identifiable lag pole or delay in the response band).
- Cross-validated: integrator K = 37.8 (multisine, GOOD link), 36.5 (multisine, WARN), 37.7 (chirp)
  over the 0.4–2.2 Hz coherent band (mean coherence 0.90–0.94) — **< 4 % spread, two excitation
  families.** Plant phase ≈ −85° in band = textbook integrator.
- K ≈ 37 is ~5× weaker than roll/pitch (165–185 *with* a pole) — yaw's weak motor drag-torque
  authority. Yaw has no fast pole because it's not thrust-differential driven.
- **Why the standard analyzer fit used to report VAF ≈ 5 % and rail:** it fits integrator+pole+delay
  (3 params); yaw has no pole/delay to find, so those railed and collapsed VAF. FIXED — the analyzer
  now has a pure-integrator (`K/s`, rel-degree-1) fallback that auto-triggers when the 3-param fit
  is poor and recomputes the IV plant at high FFT resolution (yaw lives below ~2 Hz). Default run
  now reports yaw K = 37.1 (VAF 72 %, 26 bins) with no flags; roll/pitch fits are unchanged.
- The earlier "closed-loop BW ≈ 0.78 Hz" was an ARTIFACT: the multisine pre-emphasis
  (`SYSID_MS_PREEMP=1.0`) dumps energy at the top of the band, so yaw's low end (0.1–0.3 Hz) was
  under-excited and the x/r −3 dB crossing landed wherever coherence kicked in. Ignore it.
- **MRAC note:** a pure integrator is **relative degree 1** — the easiest case for direct MRAC
  (SPR trivially satisfiable, standard adaptive law). Roll/pitch are rel-degree 2 + delay (harder).

### Capture conditions (record these every campaign — they shift the model)
- **Battery**: actuator gain scales with pack voltage; log `id.vbat` and note the band.
  Roll campaign ran at a nominal mid-pack voltage (see logs). Gain `K` drift run-to-run is
  partly voltage. MRAC online adaptation is designed to absorb this.
- **Sample rate**: auto-detected per log from `id.sample_counter` vs host time (was ~230–270 Hz
  pre-fix; should read a stable ~200 Hz after the Send_Task pacing fix).
- **Mode**: shadow mode (MRAC output injection OFF) → plant input = `u_nom`.

---

## How to reproduce / update

```bash
# per-log analysis -> ground_station/analysis/<logname>/{report.md, sysid_*.png}
python ground_station/scripts/sysid_analysis.py ground_station/logs/<log>.csv --axis roll
```
Then copy the headline numbers from the new `report.md` into the table above and move the
old row to History.

## History

- **2026-06-17 chirp ×4** (superseded as headline by 06-18 multisine, retained as cross-check):
  `ref_model_bw ≈ 39.3 rad/s`, K ≈ 185, p ≈ 15.2 rad/s (2.4 Hz), T ≈ 12 ms, VAF ≈ 100 %,
  spread < 0.1 %. First validated roll model; pre-dated the 200 Hz pacing + pre-emphasis fixes.
