# System-ID analysis — sysid_yaw_1781792793.csv

> ⚠️ **LINK QUALITY BAD — results may be UNRELIABLE.** Only 57% of frames were received (23 gaps; largest clean segment 1294 samples). The wireless link dropped frames — fly the drone closer to the receiver and re-run.

- **Source log**: `ground_station\logs\sysid_yaw_1781792793.csv`
- **Link quality**: BAD (57% frames received, 23 gaps, largest clean segment 1294 samples)
- **Sample rate (auto)**: 199.7 Hz
- **Excitation**: multisine  (dither peak 54.8, crest factor 3.11)
- **Battery (operating point)**: 0.00 V mean, 0.00→0.00 V (sag 0.00 V over run). Actuator gain scales with voltage — note this when comparing K across runs.

## Yaw axis

- Closed-loop −3 dB bandwidth: **0.780 Hz**  →  recommended `ref_model_bw` = **4.90 rad/s**
- Plant model  `G(s) = K / (s·(1 + s/p))·e^(−sT)`:
    - K (integrator gain) = 32.5
    - lag pole p = 1000.0 rad/s (159.15 Hz)
    - transport delay T = 0 ms
    - fit quality **VAF = 16.1%** over 4 coherent bins
- Samples used: 1294 (largest gap-free segment)

![yaw Bode](sysid_yaw.png)
