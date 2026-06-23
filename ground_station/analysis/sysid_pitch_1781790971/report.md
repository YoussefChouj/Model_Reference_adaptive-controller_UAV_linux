# System-ID analysis — sysid_pitch_1781790971.csv

> ⚠️ **LINK QUALITY BAD — results may be UNRELIABLE.** Only 75% of frames were received (14 gaps; largest clean segment 3984 samples). The wireless link dropped frames — fly the drone closer to the receiver and re-run.

- **Source log**: `ground_station\logs\sysid_pitch_1781790971.csv`
- **Link quality**: BAD (75% frames received, 14 gaps, largest clean segment 3984 samples)
- **Sample rate (auto)**: 199.6 Hz
- **Excitation**: multisine  (dither peak 25.0, crest factor 3.28)
- **Battery (operating point)**: 0.00 V mean, 0.01→0.00 V (sag 0.01 V over run). Actuator gain scales with voltage — note this when comparing K across runs.

## Pitch axis

- Closed-loop −3 dB bandwidth: **7.798 Hz**  →  recommended `ref_model_bw` = **49.00 rad/s**
- Plant model  `G(s) = K / (s·(1 + s/p))·e^(−sT)`:
    - K (integrator gain) = 183.5
    - lag pole p = 18.2 rad/s (2.89 Hz)
    - transport delay T = 12 ms
    - fit quality **VAF = 98.6%** over 9 coherent bins
- Samples used: 3984 (largest gap-free segment)

![pitch Bode](sysid_pitch.png)
