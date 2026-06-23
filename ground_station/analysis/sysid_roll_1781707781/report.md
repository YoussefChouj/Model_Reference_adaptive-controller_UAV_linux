# System-ID analysis — sysid_roll_1781707781.csv

- **Source log**: `..\logs\sysid_roll_1781707781.csv`
- **Sample rate (auto)**: 266.9 Hz
- **Excitation**: chirp  (dither peak 35.0, crest factor 1.46)

## Roll axis

- Closed-loop −3 dB bandwidth: **6.255 Hz**  →  recommended `ref_model_bw` = **39.30 rad/s**
- Plant model  `G(s) = K / (s·(1 + s/p))·e^(−sT)`:
    - K (integrator gain) = 176.1
    - lag pole p = 14.8 rad/s (2.35 Hz)
    - transport delay T = 12 ms
    - fit quality **VAF = 99.9%** over 7 coherent bins
- Samples used: 8829 (largest gap-free segment)

![roll Bode](sysid_roll.png)
