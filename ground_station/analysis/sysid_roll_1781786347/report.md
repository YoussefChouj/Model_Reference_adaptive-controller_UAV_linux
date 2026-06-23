# System-ID analysis — sysid_roll_1781786347.csv

- **Source log**: `ground_station\logs\sysid_roll_1781786347.csv`
- **Sample rate (auto)**: 199.5 Hz
- **Excitation**: multisine  (dither peak 39.9, crest factor 3.45)
- **Battery (operating point)**: 0.00 V mean, 0.00→0.00 V (sag 0.00 V over run). Actuator gain scales with voltage — note this when comparing K across runs.

## Roll axis

- Closed-loop −3 dB bandwidth: **7.014 Hz**  →  recommended `ref_model_bw` = **44.07 rad/s**
- Plant model  `G(s) = K / (s·(1 + s/p))·e^(−sT)`:
    - K (integrator gain) = 183.5
    - lag pole p = 16.7 rad/s (2.66 Hz)
    - transport delay T = 12 ms
    - fit quality **VAF = 99.1%** over 10 coherent bins
- Samples used: 4472 (largest gap-free segment)

![roll Bode](sysid_roll.png)
