# System-ID analysis — sysid_pitch_1781789739.csv

- **Source log**: `ground_station\logs\sysid_pitch_1781789739.csv`
- **Sample rate (auto)**: 199.7 Hz
- **Excitation**: multisine  (dither peak 45.0, crest factor 3.32)
- **Battery (operating point)**: 0.00 V mean, 0.00→0.00 V (sag 0.00 V over run). Actuator gain scales with voltage — note this when comparing K across runs.

## Pitch axis

- Closed-loop −3 dB bandwidth: **0.780 Hz**  →  recommended `ref_model_bw` = **4.90 rad/s**
- Plant model  `G(s) = K / (s·(1 + s/p))·e^(−sT)`:
    - K (integrator gain) = 151.1
    - lag pole p = 22.8 rad/s (3.62 Hz)
    - transport delay T = 16 ms
    - fit quality **VAF = 96.5%** over 8 coherent bins
- Samples used: 1451 (largest gap-free segment)

![pitch Bode](sysid_pitch.png)
