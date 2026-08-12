---
title: "Dimensionless Policies — Transfer via Buckingham π Theorem"
type: literature
tags: [dimensionless-transfer, buckingham-pi, policy-transfer, dimensional-analysis, theory, thesis]
created: 2026-08-12
sources: [arXiv:2307.15852, Girard 2024 Mathematics]
---

Raw ar5iv source: raw/papers/2026-08-12-Girard-2024-DimensionlessPolicies-arxiv2307.15852.md

## Paper Identity

Alexandre Girard. *Mathematics* 2024, 12(5), 709. DOI: 10.3390/math12050709. Code: `alx87grd/DimensionlessPolicies`.

## Core Claim

Any motion-control policy solvable in one physical system can be expressed in dimensionless form and transferred exactly (no approximation) to any dynamically similar system via Buckingham π theorem scaling — provided dimensional similarity is maintained.

## Method

- Derive dimensionless π-groups from the system's governing equations.
- Express the control law in terms of dimensionless states and parameters.
- Scale back to target system using the π-groups.
- Validated on: inverted pendulum swing-up, car steering.

**Key equation:** If two systems have identical dimensionless dynamics, the same dimensionless control policy achieves identical dimensionless tracking. Physical scaling is exact — not learned, not approximated.

## Relevance to thesis

DIRECT — this is the dimensionless prior art that ADR-0014 cites. Girard proves that dimensionless transfer is theoretically exact, not heuristic. Your "dimensionless MRAC weight vectors via `1/K` matching" is the application of this principle to adaptive control.

## Key differences from your work

- Girard transfers a full policy (deterministic control law). You transfer adaptive weight vectors.
- Girard requires exact dimensional similarity. Your framework allows parameterised similarity (scenario-relative).
- Girard has no adaptation online — transfer happens offline. You adapt online after transfer.
- Girard does not address stochasticity, disturbance rejection, or trajectory density.

## What to grill on

1. Is the "exact transfer" claim broken by unmodelled dynamics? Girard assumes the governing equations are known.
2. Can dimensionless policies handle the mismatch between simulation and hardware without adaptation?
3. Your "scenario-relative" parameterisation — is it a generalisation of Girard's exact similarity condition, or a weakening that loses the exactness guarantee?
4. Does Girard's framework extend to the 6-DOF quadrotor with attitude coupling?
