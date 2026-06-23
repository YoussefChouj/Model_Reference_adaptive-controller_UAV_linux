# System-ID analysis — sysid_roll_1781707737.csv

- **Source log**: `..\logs\sysid_roll_1781707737.csv`
- **Sample rate (auto)**: 266.9 Hz
- **Excitation**: chirp  (dither peak 35.0, crest factor 1.46)

## Roll axis

- Closed-loop −3 dB bandwidth: **6.257 Hz**  →  recommended `ref_model_bw` = **39.31 rad/s**
- Plant model  `G(s) = K / (s·(1 + s/p))·e^(−sT)`:
    - K (integrator gain) = 186.6
    - lag pole p = 15.0 rad/s (2.39 Hz)
    - transport delay T = 12 ms
    - fit quality **VAF = 99.9%** over 7 coherent bins
- Samples used: 8830 (largest gap-free segment)

![roll Bode](sysid_roll.png)
