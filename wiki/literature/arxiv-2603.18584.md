## arxiv:2603.18584 — MRAC for Gust Load Alleviation on Flexible Aircraft
**Relevance to thesis:** HIGH — directly addresses MRAC adaptation-rate tuning, Lyapunov P‑matrix design, and stability under mismatch, all core to Phase‑2 offline derivation and larger‑mismatch experiments.
**Contribution:** A systematic study of the adaptation rate Γ in MRAC for gust load alleviation, showing its impact on convergence, load reduction, and actuator demand, and proposing gain‑scheduling guidelines for discrete vs. continuous disturbances.
**Method:** Lyapunov‑based MRAC with scalar adaptation rate Γ = γQ (γ ∈ [0.01,1.0]); reference model designed with increased damping; stability condition links Lipschitz bound to Lyapunov P‑matrix; discrete‑time implementation via 4th‑order Runge–Kutta.
**Key results:**
- MRAC with Γ = 1.0Q achieves 29.45% wing‑tip deflection reduction under discrete gust, outperforming H∞ (23.15%) (p15).
- Larger Γ speeds convergence but risks oscillations; smaller Γ improves noise robustness (p7, p12).
- Stability condition: ‖F_NR(x)−F_NR(x_m)‖ ≤ λ_min(Q)/(2‖P‖) ‖x−x_m‖ (Eq. 25) guides reference‑model damping and P design (p15).
- Gain‑scheduling Γ: high Γ for discrete gusts, moderate Γ≈0.1Q for stochastic turbulence (p14).

**Relevant to YOUR work (with pages):**
- Adaptation rate parameterization Γ = γQ simplifies tuning to a single scalar γ, tested in [0.01,1.0] — directly applicable to our MRAC rate‑loop tuning (p7).
- Lyapunov P‑matrix design: P solves A_m^T P + P A_m = –Q, and stability condition λ_min(Q)/(2‖P‖) provides a principled way to choose reference‑model bandwidth and Q (p15, p5).
- Reference model selection with increased damping ratios guides desired closed‑loop behaviour; our Phase‑2 task of setting `ref_model_bw` can adopt a similar damping‑based design (p9, p4).
- Adaptation law ˙θ = –Γ φ e^T P B_c (Eq. 20) is implementable on STM32; discrete‑time MRAC via 4th‑order Runge–Kutta with matching ∆t shows lightweight real‑time feasibility (p6, p7).
- Gain‑scheduling concept: increase Γ when a discrete gust (or large tracking error) is detected, reduce during continuous turbulence — analogous to our need for robustness under larger mismatch (p14).
- Stability condition for nonlinear terms (Eq. 25) directly informs our offline P‑matrix derivation to ensure bounded tracking under plant/model mismatch (p15, p6).

**How to apply / next step:**
- Implement the scalar Γ = γQ parameterization in our MRAC firmware and sweep γ to find the optimal convergence‑vs‑actuator‑demand trade‑off for rate loops (p7, p12).
- Use the Lyapunov P‑matrix design condition (Eq. 25) to derive a principled mapping from identified inner‑loop bandwidth to `ref_model_bw` and Q, replacing the current 80–90% heuristic (p15, p5).
- Explore gain‑scheduling of Γ based on tracking‑error magnitude or detected mismatch as a robustness mechanism for larger plant/model mismatch scenarios (p14).

---
*source:* https://arxiv.org/abs/2603.18584 · *17 pp* · *reviewer:* `deepseek/deepseek-v4-pro`
