# System-ID analysis — sysid_roll_1781708024.csv

- **Source log**: `..\logs\sysid_roll_1781708024.csv`
- **Sample rate (auto)**: 263.8 Hz
- **Excitation**: multisine  (dither peak 31.7, crest factor 3.33)

## Roll axis

- Closed-loop −3 dB bandwidth: **7.214 Hz**  →  recommended `ref_model_bw` = **45.33 rad/s**
- Plant model  `G(s) = K / (s·(1 + s/p))·e^(−sT)`:
    - K (integrator gain) = 171.0
    - lag pole p = 21.0 rad/s (3.34 Hz)
    - transport delay T = 13 ms
    - fit quality **VAF = 99.6%** over 7 coherent bins
- Samples used: 3235 (largest gap-free segment)

![roll Bode](sysid_roll.png)
