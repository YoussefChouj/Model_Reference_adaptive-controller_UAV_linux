---
title: Adaptive Basis & Weight-Convergence Prior Art
type: concept
tags: [adaptive-control, literature, concurrent-learning, persistent-excitation, thesis-scope]
created: 2026-08-02
updated: 2026-08-02
sources: []
related_files: [API/mrac.c:263, API/mrac.c:286, API/mrac.h:90]
---

The named literature covering the ideas this project keeps re-deriving: making `Theta` converge
without persistent excitation, storing per-maneuver priors, and replacing the fixed basis with a
learned one. Assembled 2026-08-02 in response to *"I don't want to recreate what others have
already discovered."* **Citations are from memory and should be verified against the papers
before being built on.**

## The four to read

### 1. Concurrent Learning MRAC — start here, in thesis scope
Chowdhary & Johnson, *"Concurrent learning for convergence in adaptive control without
persistency of excitation"*, CDC 2010 (and Chowdhary's PhD thesis).

Keeps a **history stack** of past `(Phi, observed response)` pairs and adds a second update term
driving `Theta` to be consistent with all of them, not only the current instant. Proves
exponential parameter convergence with **no persistent excitation** — only a rank condition on the
recorded data.

This is the direct answer to [[parameter-drift-and-bursting]]. The geometric content is simple:

```
   hover      Phi = (1, 0.4),  needs 0.5   ->   Theta[0] + 0.4*Theta[4] = 0.5
   rolling    Phi = (1, 0.9),  needs 0.5   ->   Theta[0] + 0.9*Theta[4] = 0.5
   ----------------------------------------------------------------------
   subtract:                                    Theta[4] = 0,  Theta[0] = 0.5
```

**One `Phi` gives a line. Two different `Phi`s give a point.** The rank condition just says "the
stored regressors span the space" — i.e. the lines are not parallel. The excitation does not have
to be happening *now*; it has to have happened *once* and still be in the stack.

Why it is the right scope for this thesis: it is a change to the update law, it is provable, and
it runs on an M4.

### 2. Composite adaptation
Slotine & Li, *"Composite adaptive control of robot manipulators"*, Automatica 1989.

Drives the weights from **both** the tracking error and a **prediction error** — how badly
`Theta·Phi` predicted the torque actually obtained. The prediction error is informative even when
tracking error is zero, which is exactly the drift case. The standard fix for weak PE.

This is a rediscovery of the user's own "closed-loop weights / every feature is a small
first-order system" idea. The per-weight first-order filter it needs already exists in the
firmware as `Whatf` at [API/mrac.c:286](../../API/mrac.c#L286), currently wired to leakage.

### 3. Multiple Model Adaptive Control / switching-and-tuning
Narendra & Balakrishnan, *"Adaptive control using multiple models"*, IEEE TAC 1997.

A bank of models/controllers with switching or blending based on which fits best — the user's
"store `Theta` priors for hover, straight line, angled, rotating, then mix" idea, with the
stability analysis already done.

### 4. GP-MRAC / RKHS-MRAC
Chowdhary, Kingravi, How & Vela — Bayesian nonparametric / kernel adaptive control.

Replaces the fixed basis with a kernel model whose **centres are chosen online**, which is the
"physics-based structured part + nonparametric part covering the gaps" architecture the user
described.

**How centres are selected:** a **novelty / linear-independence test.** When a new state arrives,
check how well its kernel feature vector can be reconstructed from the existing centres. Small
residual ⇒ redundant, discard. Large residual ⇒ genuinely new region, promote to a centre. A fixed
budget caps the count; when full, the least-informative centre is evicted. Lineage: Csató & Opper
sparse online GP, Engel's KRLS.

## Adjacent but out of scope

**Motion primitive libraries** — Frazzoli, Dahleh & Feron (maneuver automaton); also trajectory
libraries (Stolle & Atkeson) and LQR-Trees (Tedrake). This matches the user's idea of decomposing
a trajectory into primitives (line + circle + …) with per-primitive priors and deterministic
per-primitive responses.

**Flagged explicitly as a scope expansion — a second thesis, not this one.** The thesis is the
adaptive layer as a controller-agnostic augmentation ([[project_thesis]] in memory). Noted here so
it is not lost, and deliberately not pursued.

## Where the contribution is still original

Concurrent learning's history stack **is a key/value memory**: stored `(Phi, response)` pairs,
queried by the current operating point. Nobody in that literature frames it that way, because
attention did not exist when it was written.

Two candidate contributions follow:

1. **Attention as a principled query over the history stack** — instead of a hard rank test and
   fixed eviction, a soft, differentiable, normalised weighting over stored operating points.
2. **A structural bound on `u_ad` from `sum(w)=1`** — the convex-hull property in
   [[attention-mechanism]] replaces the projection clamp on `Theta` with an a-priori guarantee that
   the adaptive command can never leave the hull of validated values.

Both are defensible as contributions rather than re-derivations, and both are testable in `sim/`
without a flight.

## A useful analogy the user brought

The redundancy is **inverse kinematics**: many joint configurations, one end-effector pose. And
the parallel carries — in IK you resolve redundancy with a secondary objective (min-norm, joint
limits); leakage-toward-a-prior is exactly that secondary objective on the adaptive law.

## Related

- [[parameter-drift-and-bursting]] — the concrete problem these solve
- [[attention-mechanism]] — the query mechanism
- [[mrac-control-law]] · [[l1-adaptive-control]] · [[matched-unmatched-uncertainty]]
