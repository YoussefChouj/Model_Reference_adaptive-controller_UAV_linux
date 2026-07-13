# Anti-windup is already implemented in the firmware; MRAC already uses the flag pattern

Established at session start (2026-07-06). The user reached video 2 (anti-windup clamping) of a
YouTube PID series and asked whether it's in the firmware. It is — `ComputePID()` (`pid.c:32–55`)
already does **two-layer anti-windup**: integral separation / conditional integration (`pid.c:36–40`,
gated by output-saturation sign *and* an `EMin` error-separation threshold) plus a hard clamp on the
accumulator `SumEMax` (`pid.c:41`), on top of per-term clamps (`UpMax`/`UiMax`/`UdMax`) and a final
`UMax`. So the series' anti-windup is not a gap to fill but a case study to *understand*.

Second key fact for the whole mission: the firmware already gates its adaptive layer behind runtime
flags (`mrac_flags.axis_enable_pitch/_roll/_yaw` in `mrac.c:510–524`) whose OFF state forces `u_ad=0`
and reproduces pure-PID behaviour. This is the exact "new feature behind a flag, default = today's
behaviour" pattern the mission wants — so future additions have a native template to copy, not invent.

**Implication for next sessions:** don't teach anti-windup as something to add. Teach it as the
reference implementation, then use the video's other variants (e.g. back-calculation / tracking
anti-windup) as the *first* flag-gated improvement exercise. User is beginner/intermediate embedded —
build the intuition (why the integrator runs away) before the math.
