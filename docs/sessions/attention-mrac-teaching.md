# Attention -> MRAC teaching session (2026-08-02)

> Moved verbatim out of CLAUDE.md on 2026-08-09 to cut per-turn
> context churn. CLAUDE.md keeps a compact index pointing here.

### Attention → MRAC teaching session (2026-08-02) — ACTIVE, nothing committed

**Format is mandatory here**: one layer per turn, physical/visual analogy, a check question,
WAIT for the answer before advancing. LaTeX does not render for this user — plain ASCII in code
blocks, worked numeric examples over symbols. See memories `feedback-teaching-style` and
`feedback-planning-style`. Running analogy: **a bank of PID gain sets blended by flight
condition** (attention = Takagi-Sugeno / LPV gain scheduling). Layers 1–8 delivered: soft lookup
table → dot-product similarity → softmax as legaliser → temperature as a gain knob → `1/√d_k` →
`W_Q/W_K/W_V` and asymmetry → time-blindness/causality → attention-as-adaptive-regressor.

**FIRMWARE FINDINGS (real, none fixed, none committed):**
1. **`API/mrac.c:73` comment is wrong.** `Phi[2] = x*tanhf(x)` is documented as *"bounded:
   saturates at high rate"*. It is NOT bounded — `tanh` saturates at 1 so `x*tanh(x) → |x|`
   (measured: x=17.5 → 17.5, still climbing). Design is fine (softened quadratic, grows slower
   than `x*|x|`); only the word "bounded" is false. Fix the comment.
2. **The learning path IS properly bounded** — `mrac.c:219-220` `denom = 1 + |Phi|²` and
   `mrac.c:263` divides by it (Narendra normalization). Effective step `|Phi|²/(1+|Phi|²)` is
   capped at 1. Without it the same error would teach **530× harder** at 17.5 rad/s than in
   hover (|Phi|² 615 vs 1.16); with it the ratio is 1.86×. An earlier claim in this session that
   the bounded-regressor hypothesis was violated was WRONG and has been corrected to the user.
3. **`mrac.c:294` `u_ad = Theta·Phi` uses RAW `Phi`, not normalized** — so the OUTPUT path is
   still unbounded in rate. Only the projection clamp on `Theta` (`What_limit`) bounds it.
   A softmax/partition-of-unity basis would bound it structurally (`sum(w)=1` ⇒ `u_ad` inside
   the convex hull of `Theta`), removing the need for the clamp.
4. **Hover null-space drift, worked through with the user.** In hover `Phi ≈ [1,0,0,0,u_nom,0]`
   → only `Phi[0]=1` and `Phi[4]=u_nom≈0.4` are live, and they are collinear. Every `Theta` on
   the line `Theta[0] + 0.4*Theta[4] = 0.5` gives identical `u_ad`. Gradient is `-s*Phi`, exactly
   PERPENDICULAR to that line, so it never pushes along it; noise walks `Theta` along it with no
   restoring force. **`u_ad` stays correct while `Theta` slides — the drift is invisible in
   telemetry.** It detonates when `Phi` changes shape: `(0.5,0.0)` and `(-0.3,2.0)` are identical
   in hover but differ **3×** once `u_nom` swings 0.4→0.9. This is the classic **bursting**
   phenomenon. `mrac.c:78`'s existing comment ("keep Phi[3] empty to prevent collinear drift")
   shows the team already hit this once.
   → Consequence for the thesis: **densely-excited reference trajectories are PROTECTIVE**; the
   dangerous profile is long hover followed by abrupt aggression.

**PRIOR ART given to the user** (he explicitly does not want to re-derive): **Concurrent Learning
MRAC** (Chowdhary & Johnson, CDC 2010 — history stack of past `(Phi, response)` pairs, proves
parameter convergence with NO persistent excitation, only a rank condition; two distinct `Phi`s
turn the solution line into a point — this is the direct answer to the drift) — **start here, it
is in thesis scope**; **Composite adaptation** (Slotine & Li 1989 = the user's own
"closed-loop weights / prediction error" idea); **Multiple Model Adaptive Control** (Narendra &
Balakrishnan 1997 = his bank-of-priors-per-maneuver idea); **GP-MRAC / RKHS-MRAC** (Chowdhary,
Kingravi, How, Vela — centres added online by a novelty/linear-independence test, budgeted, least
informative evicted; lineage Csató & Opper sparse online GP, Engel KRLS — VERIFY against papers).
Motion-primitive libraries (Frazzoli/Dahleh/Feron) match his trajectory-decomposition idea but
were flagged to him as a **scope expansion, a second thesis** — note and leave.

**Where his contribution is still his**: concurrent learning's history stack IS a key/value memory;
attention is a principled way to query it. Nobody in that literature frames it that way. Combined
with the `sum(w)=1` structural bound on `u_ad` (replacing the projection clamp), that is a
defensible contribution rather than a re-derivation.

**Also noted**: `API/mrac.h:90-94` already has an unstructured **RBF** branch behind
`USE_STRUCTURED_UNCERTAINTY == 0` (`MAX_NUM_BASIS = 2*NUM_BASIS + 2`) — the localized-basis path
exists as a compile option. `mrac.c:286` `Whatf` already runs one first-order filter per weight at
`gam_f` — the per-weight closed-loop structure the user described, currently wired to leakage
rather than to a prediction error.

**DRIFT SIM RUN (2026-08-02)** — 400 Hz, 600 s, `Phi=[1,0.4]`, `d=0.5`, real law incl. `denom`:
**noiseless → `Theta` does not move at all** (`(0.500,0.000)` start and finish; the user's
intuition was right for the clean case). **With 3% sensor noise → `(0.500,0.000)` drifts to
`(0.455,0.109)`**, null coordinate `+0.186 → +0.068` and still moving at 600 s, while `u_ad`
stayed inside 0.4975…0.5013 the whole time — invisible in telemetry. Burst when `u_nom` swings
0.4→0.9: `0.455 + 0.9*0.109 = 0.553` vs 0.500 = **+10.6% command error**. Drift is **monotonic,
not diffusive** (`Phi` noise correlates with error noise), so it does not self-correct.

**WIKI INGESTED (2026-08-02)**: `wiki/concepts/attention-mechanism.md`,
`wiki/concepts/parameter-drift-and-bursting.md`, `wiki/concepts/adaptive-basis-prior-art.md`;
`wiki/index.md` + `wiki/log.md` updated; `sync_obsidian.py` run (75 pages). All untracked in git.

**NEXT ACTION**: continue the layered teaching — Layer 9 is the concrete softmax-as-`Phi`
construction (bounded regressor, localized learning, convex-hull bound on `u_ad`) and how
concurrent learning's history stack maps onto keys/values.
