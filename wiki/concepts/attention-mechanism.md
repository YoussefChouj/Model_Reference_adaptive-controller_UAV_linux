---
title: Attention Mechanism (read as gain scheduling)
type: concept
tags: [machine-learning, adaptive-control, gain-scheduling, interpolation, thesis]
created: 2026-08-02
updated: 2026-08-02
sources: []
related_files: [API/mrac.c:263, API/mrac.c:294, API/mrac.h:90]
---

Attention is **interpolation between stored operating points**. Strip the ML vocabulary and it is
a Takagi–Sugeno / LPV gain-scheduled blender: a query is compared against a set of keys to produce
normalised weights, and those weights blend a set of values. Every measurement on this page was
run during the 2026-08-02 session; none of it is quoted from a paper.

## The mapping to control

| Attention word | Control equivalent |
|---|---|
| query `q` | current operating point (e.g. `vbat`, throttle, rate) |
| keys `k_j` | the conditions each stored entry was tuned at |
| values `v_j` | what that entry stores (a gain set, a `Theta` vector) |
| `softmax(qKᵀ/√d)` | normalised membership functions |
| `w @ V` | the gain-scheduled blend |
| `1/√d_k` | membership sharpness |

This is an identity, not an analogy. A Takagi–Sugeno fuzzy system is `y = Σ μ_j(x)·(local model_j)`
with `Σ μ_j = 1, μ_j ≥ 0` — exactly what attention computes. **Consequence: TS/LPV stability theory
(common quadratic Lyapunov function, one LMI per local model) already applies.** A proof route
exists; it would not have to be invented.

The only real difference from classic gain scheduling is authorship: in gain scheduling *you*
place the operating points; in attention they are fitted from data.

## The two laws every weight must obey

```
   w_i >= 0        and        sum(w_i) = 1
```

Both are required. Sum-to-one alone is not enough — with `w = [2.0, -1.0, 0.0]` (which sums to 1)
and stored gains `[100, 115, 135]` you get `Kp = 85`, a value outside every gain ever tested.
**Non-negativity is what turns extrapolation into interpolation.**

### The convex-hull bound (the safety property)

Because the weights are non-negative and sum to one, the output is a weighted average, so

```
   ||out_i||  <=  max_j ||v_j||
```

Measured: 3000 random queries scaled ×50 against a fixed `V` produced a worst output norm of
**3.530** against a `max ||V||` bound of **3.530** — exactly the bound, never past it.

- **Good:** the output can never be larger than the largest stored value. An MLP has no such bound.
- **Bad:** attention cannot extrapolate. Outside the hull of stored values it returns the nearest
  hull point, confidently and wrongly.
- **Note:** a residual connection `x + attn(x)` **destroys** this bound. Use attention without a
  residual if the bound is what you want.

## Softmax as a legaliser

Raw scores obey neither law (cosine runs −1..+1 and does not sum to 1). Softmax fixes both:
`exp()` forces positivity unconditionally; dividing by the sum forces the total to 1.

`exp` converts an *additive* score gap into a *multiplicative* weight ratio — one point of score
is always worth `e ≈ 2.718×` more weight.

### Shift invariance — softmax has perfect common-mode rejection

```
   softmax([2,1,0]) == softmax([12,11,10]) == softmax([1002,1001,1000]) == [0.665, 0.245, 0.090]
```

Only the **gaps** matter; the absolute level cancels out of the ratio. Like a differential
amplifier, softmax is blind to the common-mode level.

This is why `scores - scores.max()` in every implementation is **free**: it changes the output by
exactly zero. It is not what makes the distribution — the division by the sum does that. It is
pure overflow armour: without it, `exp(1002)` overflows to `inf` and the result is `[nan, nan, nan]`.

## Temperature is a gain knob

Put a scalar `g` on the scores before `exp` (ML writes it as `softmax(s/T)`, `g = 1/T`). Measured
with 100 keys, one perfect match scoring 1.0 and 99 others at 0.0:

| gain `g` | weight on the perfect match | effective entries in the blend |
|---|---|---|
| 0.1 | 0.0110 | 100.0 |
| 1.0 | 0.0267 | 99.0 |
| 5.0 | 0.5999 | 12.3 |
| 10.0 | 0.9955 | 1.1 |
| 20.0 | 1.0000 | 1.0 |

The two ends are the two classic gain-scheduling failures: **`g → ∞` is a hard `if/else` lookup
table** (and its chatter at the switching boundary); **`g → 0` is the flat average of every stored
gain set, in every flight condition**. Softmax is `argmax` with the corner rounded off, and `g`
sets the radius.

Note the 100-key problem is real and standard attention does **not** fix it — after normalisation
scores are clamped to `[−1, +1]`, and that range does not know how many keys you have.

## `1/√d_k` makes sharpness independent of feature count

`q·k` is a sum of `d_k` signed products — a drunkard's walk. It grows as `√d_k` on its own:

| `d_k` | measured spread of `q·k` | `√d_k` |
|---|---|---|
| 8 | 2.82 | 2.83 |
| 64 | 8.03 | 8.00 |
| 512 | 22.57 | 22.63 |

Without the division, **adding a feature silently cranks the sharpness dial toward `argmax`**.
Measured saturation with 16 keys (max entropy 2.773 nats):

| `d_k` | scaled: max w / entropy | unscaled: max w / entropy |
|---|---|---|
| 8 | 0.239 / 2.370 | 0.558 / 1.317 |
| 512 | 0.245 / 2.356 | 0.951 / 0.122 |
| 4096 | 0.249 / 2.356 | 0.977 / 0.052 |

It is a **unit correction**, not a tunable — which is why it is a hard-coded constant.

> **Same engineering move as `denom = 1 + |Phi|²` in [[parameter-drift-and-bursting]].** Something
> grows on its own and contaminates behaviour, so divide it out. `√d_k` makes softmax sharpness
> independent of feature count; `1+|Phi|²` makes MRAC learning rate independent of flight
> aggressiveness.

## Dot product measures alignment × magnitude

`q·k = ||q|| ||k|| cos θ`. It conflates "similar" with "large". Measured with `q=(0.5,0.9)` and
keys on the throttle axis — identical direction, lengths 0.5/1.0/2.0 — scores came out
0.25/0.50/1.00, in exact proportion to length. The **farthest** key ranked **2nd**; the
second-closest ranked **last**.

Two distinct fixes, both needed:

| fix | stops |
|---|---|
| per-feature scaling | one *axis* dominating (mixing volts ~15 with throttle ~0.5 gives a ~500:1 imbalance and the throttle axis becomes invisible) |
| per-vector normalisation | one *key* dominating purely by being long |

LayerNorm does the second: it pins every vector to length exactly `√d`, so ranking by dot product
becomes ranking by angle.

## `Q = K = V` is a no-op

With `Q = K`, the score matrix diagonal is `x_i·x_i` — a sum of **squares**, so nothing cancels and
it grows as `d_k`. Off-diagonals are signed sums and grow only as `√d_k`. Measured:

| `d_k` | diagonal | off-diagonal | ratio | resulting self-attention weight |
|---|---|---|---|---|
| 8 | 7.9 | 2.2 | 3.6× | **0.737** |
| 32 | 31.8 | 4.5 | 7.1× | 0.970 |
| 128 | 127.7 | 9.0 | 14.3× | **1.000** |

At `d_k = 128`, `attention(X,X,X)` is *exactly* an identity function. The learned projections
`W_Q, W_K, W_V` are not decoration — they let the three roles ask different questions of the same
data ("what do I need?" / "what do I have?" / "what do I deliver?").

### Asymmetry is why `W_Q ≠ W_K` matters

`X @ X.T` is symmetric by construction (`a·b = b·a`), so it can **never** express one-way
relevance. But relevance often is one-way — a richly-excited aggressive log is informative about
hover; a hover log says nothing about aggressive flight (see [[persistent-excitation]] in
[[parameter-drift-and-bursting]]). Measured with distinct `W_Q`/`W_K`:
`score(query=hover, key=aggressive) = 3.0` while `score(query=aggressive, key=hover) = 1.0`.

## Attention is blind to time

`attention(shuffle(X)) = shuffle(attention(X))`. Measured on a 5-sample telemetry window: a rate
**climbing** 10→90 deg/s and one **collapsing** 90→10 deg/s (identical samples, reversed) produced
mean-pooled outputs identical to **8.9e-17**.

So attention cannot see a derivative, a rate of change, a direction of travel, an oscillation
frequency or phase — every quantity a controller is built from. A state-space model has time
welded into its algebra; attention has an unordered bag of vectors.

Three fixes, in increasing order of preference for control work:

1. **Positional encoding** — bolt "when did this happen" on as features.
2. **Causal mask** (`-inf` above the diagonal) — required anyway for online use, since unmasked
   attention reads the future. Measured bonus: the mask is tied to *position*, not content, so it
   breaks the permutation symmetry by itself (0.428 difference on a window that was otherwise
   identical). This is the published "decoder-only transformers learn position from the mask" result.
3. **Just compute the feature** — feed `e[k] - prev_e` in directly. Exact, free, ~2 instructions
   on the M4. *Never make a learned system rediscover arithmetic you can compute exactly.*

## Cost on an STM32F407

`4·n²·d_k` FLOPs per inference; ~168 MFLOP/s optimistic on the M4 FPU.

| window `n` | `d_k` | FLOP/inference | @400 Hz | % of core |
|---|---|---|---|---|
| 4 | 8 | 512 | 0.20 MFLOP/s | 0.1% |
| 20 | 32 | 51 200 | 20.5 MFLOP/s | **12.2%** |
| 50 | 64 | 640 000 | 256 MFLOP/s | 152% ✗ |
| 128 | 64 | 4.2 M | 1678 MFLOP/s | 999% ✗ |

**A small attention block is feasible; a Transformer is not.** The `n²` wall arrives around
`n ≈ 30`. Not in the table: `expf()` costs roughly 50–100 cycles on Cortex-M4 (estimate, not
measured on this target), so at `n = 20` the softmax alone is ~7% of the core — comparable to the
matmuls. A real implementation needs a piecewise-linear `exp` or a LUT.

## Structural mapping onto this firmware's MRAC

```
   FIRMWARE (API/mrac.c:294)          ATTENTION
   u_ad = Σ Theta[i] * Phi[i]         out = Σ  V[i]  *  w[i]
```

`Theta` ↔ `V` (stored values), `Phi` ↔ `w` (weights). And at [API/mrac.c:263](../../API/mrac.c#L263)
`grad[i] = -s*Phi[i]/denom` — **`Phi[i]` gates learning**: if `Phi[i]` is zero, weight `i` does not
move this tick regardless of error size. `Phi` decides not only what the controller outputs but
what it *learns* and where it stores it.

Using a softmax as `Phi` would buy three things this firmware currently gets by other means or not
at all:

1. **Bounded regressor by construction** (`sum(w)=1`, each `w ∈ [0,1]`).
2. **Localised learning** — hover errors stop overwriting maneuver knowledge. See
   [[parameter-drift-and-bursting]].
3. **A structural bound on `u_ad`** via the convex hull, replacing the projection clamp. This
   matters because [API/mrac.c:294](../../API/mrac.c#L294) uses **raw** `Phi`, not the normalised
   one, so the output path is currently unbounded in rate.

The codebase already has the hook: [API/mrac.h:90](../../API/mrac.h#L90) carries an unstructured
**RBF** branch behind `USE_STRUCTURED_UNCERTAINTY == 0`.

Note also: attention with an exponential-dot-product kernel **is** Nadaraya–Watson kernel
regression (verified numerically to 9.7e-17 against an explicit kernel smoother), and when query
and key norms are constant it reduces exactly to a Gaussian RBF. Attention is a normalised RBF
network with learned centres.

## Related

- [[parameter-drift-and-bursting]] — the firmware defect this was applied to
- [[adaptive-basis-prior-art]] — concurrent learning, composite adaptation, MMAC, GP-MRAC
- [[mrac-control-law]] · [[l1-adaptive-control]] · [[matched-unmatched-uncertainty]]
