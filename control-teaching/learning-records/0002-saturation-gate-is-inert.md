# The firmware's PID saturation anti-windup gate is effectively inert

Taught in Lesson 2 (2026-07-06). In `ComputePID()` (`pid.c:36–40`), the integral-accumulation
condition's clause [A] — `((U <= UMax && E>0) || (U >= -UMax && E<0))` — can never block, because
`pPID->U` is only ever written at the end of the same function and clamped to `[-UMax, UMax]` (line 52),
and no other code writes it. So on entry the invariant `-UMax <= U <= UMax` always holds, making clause
[A] always true for any `E != 0`. The accumulation condition therefore collapses to just clause [B],
integral separation: `ABS(E) < EMin`.

**Consequence:** the real windup protection in the rate loops is (1) integral separation via a small
`EMin` and (2) the accumulator hard-clamp `SumEMax` — NOT saturation-aware clamping. True clamping /
back-calculation needs the *pre-saturation* vs *post-saturation* output difference, which this code
never forms because both are the same clamped variable. Real actuator saturation lives downstream at
the motor mixer, invisible to `UMax`.

**Implication for next sessions:** this is the user's designated FIRST flag-gated improvement —
back-calculation anti-windup inserted right after `pid.c:52`, gated by a flag whose OFF state is
bit-identical to today, testable in `sim/` (RatePID is parity). This supersedes the Lesson-1-era framing
in [[0001-anti-windup-already-present]] that treated the firmware's anti-windup as a complete two-layer
reference — it's really one-and-a-half layers. Also worth eventually noting in the repo wiki
(`wiki/theory/cascaded-pid.md` currently describes [A] as functional).

Corrected a would-be misconception before it cost anything: the user should not assume the wiki's
"two-layer anti-windup" claim is fully accurate.
