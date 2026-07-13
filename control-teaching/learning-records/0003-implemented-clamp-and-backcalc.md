# Implemented AW_CLAMP and AW_BACKCALC anti-windup behind a per-PID flag

Session 2026-07-06. User asked to implement both a correct clamping mechanism and a back-calculation
observer. Done in firmware, default OFF:

- `robot_types.h`: added `PID_AntiWindup_e { AW_LEGACY=0, AW_CLAMP=1, AW_BACKCALC=2 }`; appended
  `int aw_mode` and `float Kt` to `PIDTypeDef` (appended → the positional initializer in `pid.c`
  zero-fills them → every loop stays legacy by default, bit-identical).
- `pid.c` `ComputePID()`: branches on `aw_mode`. Legacy is the untouched `else`. CLAMP = tentative
  integrate + revert on real saturation with sign-match (no EMin). BACKCALC = always integrate +
  `SumE += Kt*(U - u_presat)` (needs Kt>0). Declarations hoisted to block tops for ARMCC V5.06 (C90).

Not yet done / open: (1) no runtime toggle — enabling requires setting `aw_mode`/`Kt` in code and
reflashing (a GS command like the existing CMD pattern would allow bench A/B without reflash);
(2) sim/ RatePID not yet mirrored, so the mandated ON-vs-OFF A/B test hasn't run — **must do before
flying**; (3) saturation is detected at rate-PID `UMax`, a proxy for the true mixer-level actuator
limit; (4) `ComputeYawPID` and `ComputePID_locx/y` are separate copies still on legacy only.

Evidence of understanding: user correctly restated the legacy mechanism (EMin separation + SumEMax clamp,
integrator freezes on large error) in their own words before implementing. Solid grasp of the concept.
This user is capable of driving the sim A/B themselves with guidance.
