# SysID analysis — roll axis

Per-log analysis folders are written here by `scripts/sysid_analysis.py`
(`<logname>/report.md` + Bode plot). This README collects batch conclusions.

---

## 2026-06-17 — roll inner-loop ID batch (single-axis v6 frame, ~230–267 Hz)

9 runs, closed-loop superimposed dither, geofence-held station, **no RECOVERY** on any run.

| Log | Excitation | Amp (°/s) | fs (Hz) | ref_model_bw (rad/s) | lag pole (Hz) | delay (ms) | VAF | Quality |
|---|---|---|---|---|---|---|---|---|
| 1781707687 | chirp | 35 | 267.2 | **39.34** | 2.43 | 12 | 99.9% | ⭐ |
| 1781707737 | chirp | 35 | 266.9 | 39.31 | 2.39 | 12 | 99.9% | ⭐ |
| 1781707781 | chirp | 35 | 266.9 | 39.30 | 2.35 | 12 | 99.9% | ⭐ |
| 1781707840 | chirp | 35 | 266.9 | 39.31 | 2.57 | 12 | 100% | ⭐ |
| 1781708024 | multisine | 35 | 263.8 | 45.33 | 3.34 | 13 | 99.6% | ok |
| 1781708069 | multisine | 35 | 230.3 | 45.21 | 2.75 | 16 | 99.2% | ok (drops) |
| 1781708122 | multisine | 35 | 246.6 | 42.36 | 2.82 | 13 | 99.8% | ok (drops) |
| 1781708174 | multisine | 35 | 245.9 | 42.25 | 2.59 | 19 | 95.1% | ok (drops) |
| 1781707964 | multisine | 25 | 248.7 | 48.82 | 2.43 | 11 | 99.4% | counter reset* |

\* 1781707964 contained a sample-counter reset (two runs in one capture); the analyzer
auto-uses the largest gap-free segment. Re-fly the 25 °/s linearity check for a clean log.

### Conclusions
- **Recommended `ref_model_bw` ≈ 39 rad/s** (6.26 Hz) — from the 4 chirps, repeatable to 0.1 %.
- **Plant structure**: integrator + single lag pole (~2.4 Hz) + ~12 ms transport delay,
  `G(s) = K / (s·(1 + s/p))·e^(−sT)`, VAF ~100 %. This is the 2nd-order(+delay) model to
  seed a higher-order MRAC reference. The old first-order `1/(b+Js)` fit returned a
  non-physical **negative J** because the measured phase passes −90°/−180° within the
  excited band — wrong model order, not bad data.
- **Excitation choice**: chirp is the robust default on this (lossy) link — it concentrates
  energy per bin and survived frame drops (coherence >0.95 to 10 Hz). Multisine is superior
  for variance reduction *once capture is clean* (no dropped frames); here it lost coherence
  above ~5 Hz due to drops + energy split across 20 tones.
- **Sample rate**: Send_Task emits ~230–267 Hz (not the 200 Hz the firmware comment claims);
  verified against the known 0.5–15 Hz tone band. Analyzer auto-detects fs per log.

### Re-run cmd
```
python scripts/sysid_analysis.py logs/<log>.csv --axis roll
```
