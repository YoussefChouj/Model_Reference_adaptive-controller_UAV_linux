# System-ID analysis — sysid_roll_1781786415.csv

- **Source log**: `ground_station\logs\sysid_roll_1781786415.csv`
- **Sample rate (auto)**: 199.4 Hz
- **Excitation**: multisine  (dither peak 38.4, crest factor 3.36)
- **Battery (operating point)**: 0.00 V mean, 0.00→0.00 V (sag 0.00 V over run). Actuator gain scales with voltage — note this when comparing K across runs.

## Roll axis

- Closed-loop −3 dB bandwidth: **7.010 Hz**  →  recommended `ref_model_bw` = **44.04 rad/s**
- Plant model  `G(s) = K / (s·(1 + s/p))·e^(−sT)`:
    - K (integrator gain) = 151.9
    - lag pole p = 21.9 rad/s (3.48 Hz)
    - transport delay T = 15 ms
    - fit quality **VAF = 98.6%** over 9 coherent bins
- Samples used: 1228 (largest gap-free segment)

![roll Bode](sysid_roll.png)
