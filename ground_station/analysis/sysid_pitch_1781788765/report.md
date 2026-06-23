# System-ID analysis — sysid_pitch_1781788765.csv

- **Source log**: `ground_station\logs\sysid_pitch_1781788765.csv`
- **Link quality**: GOOD (100% frames received, 0 gaps, largest clean segment 8602 samples)
- **Sample rate (auto)**: 199.6 Hz
- **Excitation**: multisine  (dither peak 45.0, crest factor 3.26)
- **Battery (operating point)**: 0.00 V mean, 0.02→0.00 V (sag 0.02 V over run). Actuator gain scales with voltage — note this when comparing K across runs.

## Pitch axis

- Closed-loop −3 dB bandwidth: **7.017 Hz**  →  recommended `ref_model_bw` = **44.09 rad/s**
- Plant model  `G(s) = K / (s·(1 + s/p))·e^(−sT)`:
    - K (integrator gain) = 170.3
    - lag pole p = 18.5 rad/s (2.95 Hz)
    - transport delay T = 13 ms
    - fit quality **VAF = 98.3%** over 9 coherent bins
- Samples used: 8602 (largest gap-free segment)

![pitch Bode](sysid_pitch.png)
