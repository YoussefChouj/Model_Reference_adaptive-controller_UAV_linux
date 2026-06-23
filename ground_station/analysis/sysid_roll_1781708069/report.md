# System-ID analysis — sysid_roll_1781708069.csv

- **Source log**: `..\logs\sysid_roll_1781708069.csv`
- **Sample rate (auto)**: 230.3 Hz
- **Excitation**: multisine  (dither peak 31.7, crest factor 3.36)

## Roll axis

- Closed-loop −3 dB bandwidth: **7.196 Hz**  →  recommended `ref_model_bw` = **45.21 rad/s**
- Plant model  `G(s) = K / (s·(1 + s/p))·e^(−sT)`:
    - K (integrator gain) = 159.0
    - lag pole p = 17.3 rad/s (2.75 Hz)
    - transport delay T = 16 ms
    - fit quality **VAF = 99.2%** over 8 coherent bins
- Samples used: 4066 (largest gap-free segment)

![roll Bode](sysid_roll.png)
