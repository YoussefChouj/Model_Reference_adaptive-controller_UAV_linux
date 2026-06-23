# System-ID analysis — sysid_roll_1781786614.csv

- **Source log**: `ground_station\logs\sysid_roll_1781786614.csv`
- **Sample rate (auto)**: 199.5 Hz
- **Excitation**: multisine  (dither peak 43.7, crest factor 3.19)
- **Battery (operating point)**: 0.00 V mean, 0.00→0.00 V (sag 0.00 V over run). Actuator gain scales with voltage — note this when comparing K across runs.

## Roll axis

- Closed-loop −3 dB bandwidth: **7.014 Hz**  →  recommended `ref_model_bw` = **44.07 rad/s**
- Plant model  `G(s) = K / (s·(1 + s/p))·e^(−sT)`:
    - K (integrator gain) = 168.3
    - lag pole p = 19.3 rad/s (3.06 Hz)
    - transport delay T = 15 ms
    - fit quality **VAF = 98.1%** over 9 coherent bins
- Samples used: 6602 (largest gap-free segment)

![roll Bode](sysid_roll.png)
