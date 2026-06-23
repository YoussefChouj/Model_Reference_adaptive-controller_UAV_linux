# System-ID analysis — sysid_roll_1781786265.csv

- **Source log**: `ground_station\logs\sysid_roll_1781786265.csv`
- **Sample rate (auto)**: 200.0 Hz
- **Excitation**: multisine  (dither peak 39.9, crest factor 3.44)
- **Battery (operating point)**: 0.00 V mean, 0.00→0.00 V (sag 0.00 V over run). Actuator gain scales with voltage — note this when comparing K across runs.

## Roll axis

- Closed-loop −3 dB bandwidth: **7.032 Hz**  →  recommended `ref_model_bw` = **44.18 rad/s**
- Plant model  `G(s) = K / (s·(1 + s/p))·e^(−sT)`:
    - K (integrator gain) = 161.9
    - lag pole p = 22.0 rad/s (3.49 Hz)
    - transport delay T = 15 ms
    - fit quality **VAF = 98.5%** over 8 coherent bins
- Samples used: 6601 (largest gap-free segment)

![roll Bode](sysid_roll.png)
