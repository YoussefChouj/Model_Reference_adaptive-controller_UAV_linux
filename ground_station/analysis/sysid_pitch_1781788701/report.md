# System-ID analysis — sysid_pitch_1781788701.csv

- **Source log**: `ground_station\logs\sysid_pitch_1781788701.csv`
- **Sample rate (auto)**: 199.7 Hz
- **Excitation**: multisine  (dither peak 45.0, crest factor 3.26)
- **Battery (operating point)**: 0.00 V mean, 0.00→0.00 V (sag 0.00 V over run). Actuator gain scales with voltage — note this when comparing K across runs.

## Pitch axis

- Closed-loop −3 dB bandwidth: **6.240 Hz**  →  recommended `ref_model_bw` = **39.20 rad/s**
- Plant model  `G(s) = K / (s·(1 + s/p))·e^(−sT)`:
    - K (integrator gain) = 176.9
    - lag pole p = 17.9 rad/s (2.85 Hz)
    - transport delay T = 13 ms
    - fit quality **VAF = 98.2%** over 9 coherent bins
- Samples used: 3610 (largest gap-free segment)

![pitch Bode](sysid_pitch.png)
