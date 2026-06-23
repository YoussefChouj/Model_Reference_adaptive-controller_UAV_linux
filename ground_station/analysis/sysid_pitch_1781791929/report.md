# System-ID analysis — sysid_pitch_1781791929.csv

> ⚠️ **LINK QUALITY BAD — results may be UNRELIABLE.** Only 79% of frames were received (14 gaps; largest clean segment 2094 samples). The wireless link dropped frames — fly the drone closer to the receiver and re-run.

- **Source log**: `ground_station\logs\sysid_pitch_1781791929.csv`
- **Link quality**: BAD (79% frames received, 14 gaps, largest clean segment 2094 samples)
- **Sample rate (auto)**: 199.6 Hz
- **Excitation**: chirp  (dither peak 35.0, crest factor 1.44)
- **Battery (operating point)**: 0.00 V mean, 0.00→0.00 V (sag 0.00 V over run). Actuator gain scales with voltage — note this when comparing K across runs.

## Pitch axis

- Closed-loop −3 dB bandwidth: **5.458 Hz**  →  recommended `ref_model_bw` = **34.29 rad/s**
- Plant model  `G(s) = K / (s·(1 + s/p))·e^(−sT)`:
    - K (integrator gain) = 166.9
    - lag pole p = 15.4 rad/s (2.45 Hz)
    - transport delay T = 10 ms
    - fit quality **VAF = 95.8%** over 5 coherent bins
- Samples used: 2094 (largest gap-free segment)

![pitch Bode](sysid_pitch.png)
