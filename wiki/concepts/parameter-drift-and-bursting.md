---
title: Parameter Drift and Bursting in this MRAC
type: concept
tags: [mrac, adaptive-control, persistent-excitation, drift, bursting, defect]
created: 2026-08-02
updated: 2026-08-02
sources: []
relations:
  - type: safety_critical_for
    target: "[[MRAC Control Law]]"
related_files: [API/mrac.c:73, API/mrac.c:78, API/mrac.c:219, API/mrac.c:263, API/mrac.c:282, API/mrac.c:294]
---

Why `Theta` wanders during a long hover even though the telemetry looks perfect, and why that
hidden drift detonates on the first aggressive maneuver. Derived from the firmware during the
2026-08-02 session; **nothing here is fixed yet**.

## The mechanism, in this firmware's own numbers

In steady hover the roll rate `x ≈ 0`, so the structured basis at
[API/mrac.c:71-89](../../API/mrac.c#L71-L89) collapses:

```
   Phi[0] = 1.0        constant, always on
   Phi[1] = x          ~ 0   (rate)
   Phi[2] = x*tanh(x)  ~ 0   (softened drag)
   Phi[3] = cross      ~ 0   (product of rates)
   Phi[4] = u_nom      ~ 0.4 (roughly constant hover command)
   Phi[5] = xm         ~ 0   (reference)
```

Two live elements, and **both are constants** — therefore collinear. If the axis needs
`u_ad = 0.5`, every one of these is a perfect solution:

```
   Theta[0]  Theta[4]      u_ad = Theta[0]*1 + Theta[4]*0.4
     0.5       0.0    ->       0.500
     0.1       1.0    ->       0.500
    -0.3       2.0    ->       0.500
     0.9      -1.0    ->       0.500
```

## Why the gradient cannot fix it

The update is `grad = -s * Phi` ([mrac.c:263](../../API/mrac.c#L263)), and `Phi = (1, 0.4)` is
exactly **perpendicular** to the solution line `Theta[0] + 0.4*Theta[4] = 0.5`.

```
   Theta[4]
      ^
    2 |  o(-0.3, 2.0)
      |   \
    1 |    o(0.1, 1.0)         THE SOLUTION LINE
      |     \                  every point gives u_ad = 0.500
    0 |      o(0.5, 0.0)       the error cannot tell them apart
      |       \
   -1 |        o(0.9, -1.0)
      +------------------------> Theta[0]

        gradient  ->  perpendicular, drives you ONTO the line, then stops (e=0)
        noise     ->  parallel, slides you ALONG it, nothing pushes back
```

A random walk with **no restoring force** in the null direction. The classic picture: six people
pushing a cart through one shared handle — you can measure the total force perfectly and never
determine who contributed what.

**This is exactly what "no persistent excitation" means**: `e → 0` proves the *sum* is right and
says nothing about the parts. `e → 0` does **not** imply `Theta → Theta*`.

**The drift is invisible in telemetry.** `u_ad` stays correct the entire time. Only `Theta` moves.

## Why it detonates later — bursting

The drift is harmless while `Phi` keeps its shape. It converts to error the instant the shape
changes — e.g. `u_nom` swinging 0.4 → 0.9 as the drone leaves hover:

```
   Theta pair       hover (u_nom=0.4)      maneuver (u_nom=0.9)
    (0.5,  0.0)   ->      0.500        ->        0.500
    (-0.3, 2.0)   ->      0.500        ->        1.500      <- 3x the command
```

Two weight sets indistinguishable for the entire hover differ **3×** the moment the geometry
moves. Which one you fly with is whatever the random walk happened to land on.

This is the standard **bursting** phenomenon in adaptive control: quiet periods let parameters
drift along unidentifiable directions, and the first sharp excitation converts that into a large
transient before re-convergence.

**It is not only hover → maneuver.** Any change in `Phi`'s shape does it — a turn, a non-uniform
trajectory segment, a payload change. Every regime has its own solution line; drifting along one
moves you off the point that was also correct on the next.

### Consequence for trajectory design

**Densely-excited reference trajectories are protective**, not dangerous — they supply the
excitation that pins `Theta` down. The dangerous profile is **long hover followed by abrupt
aggression**. Relevant to any thesis experiment that starts with a settle-and-hover phase.

### The team already met this once

[API/mrac.c:78](../../API/mrac.c#L78) carries the comment *"keep Phi[3] empty to prevent collinear
drift"*. The collinearity hazard is known in this codebase; the `Phi[0]`/`Phi[4]` pair in hover is
the same hazard, unaddressed.

## Narendra normalization — what `denom` actually does

[API/mrac.c:219-220](../../API/mrac.c#L219-L220):

```c
    Phi_sq = MRAC_VectorNormSquare(state->Phi, MAX_NUM_BASIS);
    denom  = 1.0f + Phi_sq;                    //  1 + |Phi|^2
    grad[i] = (-s * state->Phi[i]) / denom;    //  Phi / (1 + |Phi|^2)
```

Work out how far `u_ad` actually moves in one tick:

```
   delta_u_ad = delta_Theta . Phi = -dt * gamma * s * |Phi|^2 / (1 + |Phi|^2)
                                                     \_____ step size _____/
```

| condition | `\|Phi\|²` | step ∝ `\|Phi\|²` (no norm) | step ∝ `\|Phi\|²/(1+\|Phi\|²)` (with norm) |
|---|---|---|---|
| hover | 1.16 | 1.16 | 0.537 |
| 17.5 rad/s roll | ~615 | 615.00 | 0.998 |
| **ratio** | | **530×** | **1.86×** |

Without it, the same tracking error would teach **530× harder** during a fast roll than in hover,
purely because `Phi` got bigger — `gamma` would be untunable. `|Phi|²/(1+|Phi|²)` can never exceed
1, so learning speed becomes roughly independent of flight aggressiveness.

Same move as `1/√d_k` in [[attention-mechanism]]: divide out the thing that grows on its own.

## Defects found, none fixed

1. **`API/mrac.c:73` comment is factually wrong.** `Phi[2] = x*tanhf(x)` is documented as
   *"bounded: saturates at high rate"*. `tanh` saturates at 1, so `x*tanh(x) → |x|` and climbs
   forever (measured: x=0.5→0.23, 1→0.76, 2→1.93, 5→5.00, 17.5→**17.50**). The *design* is fine —
   it is a softened quadratic, growing slower than `x*|x|` — only the word "bounded" is false.
   Fix the comment before it misleads someone into thinking the stability hypothesis is met by
   `Phi` itself.
2. **`API/mrac.c:294` uses raw `Phi`, not the normalised one.** So while the *learning* path is
   properly bounded (see above), the *output* `u_ad = Theta·Phi` still grows with rate. The only
   bound there is the projection clamp on `Theta` (`What_limit`) — bolted on, not structural. A
   partition-of-unity basis (`sum(w)=1`) would bound it by construction; see the convex-hull
   section of [[attention-mechanism]].

> **Correction recorded:** an earlier claim in this session that the bounded-regressor hypothesis
> of the MRAC proof was violated was **wrong**. The proof's condition is on the normalised
> regressor `Phi/(1+|Phi|²)`, which line 220 supplies and which is bounded by 0.5. Only the
> comment and the output path are at fault.

## Two fixes, and what each leaves open

| fix | stops the random walk by | leaves unresolved |
|---|---|---|
| **leakage toward a stored prior** | adding a restoring force in the null direction | you must supply the prior — and it is only as good as your estimate |
| **localised basis** (RBF / softmax) | preventing hover errors from touching maneuver weights | redundancy still exists *within* a region; does not say where `Theta` should be |
| **concurrent learning** | intersecting the solution lines from several stored operating points | needs a history stack and a rank condition — see [[adaptive-basis-prior-art]] |

Only the first two were the user's own ideas. The third **derives** the target from recorded data
instead of requiring a prior — the same idea minus the hardest part.

## Existing hooks in the codebase

- [API/mrac.h:90-94](../../API/mrac.h#L90-L94) — unstructured **RBF** branch behind
  `USE_STRUCTURED_UNCERTAINTY == 0`, `MAX_NUM_BASIS = 2*NUM_BASIS + 2`. The localised-basis path
  already exists as a compile option.
- [API/mrac.c:286](../../API/mrac.c#L286) — `Whatf` runs one first-order filter per weight at
  `gam_f`. This is exactly the per-weight closed-loop structure needed for composite adaptation;
  it is currently wired to leakage, not to a prediction error.

## Measured (2026-08-02)

Two live weights, `Phi = [1, 0.4]` plus sensor noise, constant unmodelled torque `d = 0.5`,
running the real law (`grad = -s*Phi/(1+|Phi|²)`, `Theta += dt*gamma*grad`) at 400 Hz for 600 s
from `Theta = (0.5, 0.0)`:

| noise | `t=0` | `t=600 s` | `u_ad` range over the run |
|---|---|---|---|
| **none** | `(0.500, 0.000)` | `(0.500, 0.000)` — **unmoved** | 0.5000 flat |
| **3%** | `(0.500, 0.000)` | `(0.455, 0.109)` | 0.4975 … 0.5013 |

**Noise is required.** Noiseless, the gradient drives onto the line, `e = 0`, and everything
stops — nothing walks. With realistic sensor noise the null coordinate moved `+0.186 → +0.068`
and was **still moving** at 600 s.

`u_ad` stayed within ±0.3% of target the entire time. **Nothing in telemetry would show this.**

The resulting burst, from those measured weights, when `u_nom` swings 0.4 → 0.9:

```
   start-of-hover  (0.500, 0.000)  ->  0.500 + 0.9*0.000 = 0.500   correct
   end-of-hover    (0.455, 0.109)  ->  0.455 + 0.9*0.109 = 0.553   +10.6%
```

A **10.6% command error on the first maneuver**, manufactured from sensor noise alone during a
hover in which the controller looked flawless. The drift is **monotonic, not diffusive** — the
`Phi` noise correlates with the error noise, which biases the walk. It does not self-correct.

## Related

- [[attention-mechanism]] · [[adaptive-basis-prior-art]] · [[mrac-control-law]]
- [[l1-adaptive-control]] — the `u_ad` low-pass is a different lever on a different problem
