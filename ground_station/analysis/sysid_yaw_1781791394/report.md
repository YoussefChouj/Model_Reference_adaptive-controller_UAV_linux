# System-ID analysis — sysid_yaw_1781791394.csv

> ⚠️ **LINK QUALITY WARN — results may be UNRELIABLE.** Only 91% of frames were received (4 gaps; largest clean segment 4695 samples). The wireless link dropped frames — fly the drone closer to the receiver and re-run.

- **Source log**: `ground_station\logs\sysid_yaw_1781791394.csv`
- **Link quality**: WARN (91% frames received, 4 gaps, largest clean segment 4695 samples)
- **Sample rate (auto)**: 199.7 Hz
- **Excitation**: multisine  (dither peak 45.0, crest factor 3.27)
- **Battery (operating point)**: 0.00 V mean, 0.00→0.00 V (sag 0.00 V over run). Actuator gain scales with voltage — note this when comparing K across runs.

## Yaw axis

- Closed-loop −3 dB bandwidth: **0.780 Hz**  →  recommended `ref_model_bw` = **4.90 rad/s**
- Plant model  `G(s) = K / (s·(1 + s/p))·e^(−sT)`:
    - K (integrator gain) = 52.1
    - lag pole p = 1000.0 rad/s (159.15 Hz)
    - transport delay T = 7 ms
    - fit quality **VAF = 49.1%** over 9 coherent bins
- Samples used: 4695 (largest gap-free segment)

![yaw Bode](sysid_yaw.png)
