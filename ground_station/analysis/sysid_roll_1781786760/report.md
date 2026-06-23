# System-ID analysis — sysid_roll_1781786760.csv

- **Source log**: `ground_station\logs\sysid_roll_1781786760.csv`
- **Link quality**: GOOD (100% frames received, 0 gaps, largest clean segment 6602 samples)
- **Sample rate (auto)**: 199.6 Hz
- **Excitation**: multisine  (dither peak 24.3, crest factor 3.19)
- **Battery (operating point)**: 0.00 V mean, 0.00→0.00 V (sag 0.00 V over run). Actuator gain scales with voltage — note this when comparing K across runs.

## Roll axis

- Closed-loop −3 dB bandwidth: **7.016 Hz**  →  recommended `ref_model_bw` = **44.09 rad/s**
- Plant model  `G(s) = K / (s·(1 + s/p))·e^(−sT)`:
    - K (integrator gain) = 148.3
    - lag pole p = 23.5 rad/s (3.74 Hz)
    - transport delay T = 17 ms
    - fit quality **VAF = 99.1%** over 8 coherent bins
- Samples used: 6602 (largest gap-free segment)

![roll Bode](sysid_roll.png)
