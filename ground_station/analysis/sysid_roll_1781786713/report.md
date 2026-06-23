# System-ID analysis — sysid_roll_1781786713.csv

- **Source log**: `ground_station\logs\sysid_roll_1781786713.csv`
- **Sample rate (auto)**: 199.6 Hz
- **Excitation**: multisine  (dither peak 43.7, crest factor 3.19)
- **Battery (operating point)**: 0.00 V mean, 0.00→0.00 V (sag 0.00 V over run). Actuator gain scales with voltage — note this when comparing K across runs.

## Roll axis

- Closed-loop −3 dB bandwidth: **7.016 Hz**  →  recommended `ref_model_bw` = **44.08 rad/s**
- Plant model  `G(s) = K / (s·(1 + s/p))·e^(−sT)`:
    - K (integrator gain) = 162.7
    - lag pole p = 18.6 rad/s (2.95 Hz)
    - transport delay T = 15 ms
    - fit quality **VAF = 98.6%** over 10 coherent bins
- Samples used: 6603 (largest gap-free segment)

![roll Bode](sysid_roll.png)
