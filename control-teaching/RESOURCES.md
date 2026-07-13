# Drone Control-Law Resources

> Sources are plural and grow over time (see MISSION.md). This list expands as we pull from papers,
> codebases, and other series — not just the current video course.

## Knowledge

- **Brian Douglas — "Understanding PID Control" series** (MathWorks Tech Talks), playlist
  [`PLn8PRpmsu08pQBgjxYFXSsODEF3Jqmm-y`](https://youtube.com/playlist?list=PLn8PRpmsu08pQBgjxYFXSsODEF3Jqmm-y)
  · [Part 2 — Anti-windup](https://www.youtube.com/watch?v=NVLXCwc8HzM). *High-trust primary source; the
  current input.* Part 2 covers **both** clamping (conditional integration) and **back-calculation**.
  Use for: PID intuition and each incremental technique, in video order.
- **MathWorks — "Understanding PID Control" hub**
  [mathworks.com/videos/series/understanding-pid-control](https://www.mathworks.com/videos/series/understanding-pid-control.html)
  Companion pages/Simulink examples for the same series. Use for: a second angle on any video's topic.
- **In-repo wiki — `wiki/theory/cascaded-pid.md`**
  Maps the 4-level cascade and every gain to its line in `pid.c`; documents the two-layer anti-windup.
  Use for: grounding any lesson in the actual firmware.
- **In-repo wiki — `wiki/concepts/mrac-control-law.md`** + `wiki/theory/` MRAC pages
  The adaptive layer: structured-basis regressor, gradient + projection, deadzone, `What` limits.
  Use for: anything touching `mrac.c`.
- **Åström & Murray, _Feedback Systems_ (2nd ed.), Ch. 11 (PID)** — free PDF at fbsbook.org
  The trusted textbook reference behind the wiki's PID theory. Use for: anti-windup back-calculation,
  derivative filtering, integrator theory when a video hand-waves the math.

### Estimation thread (opened 2026-07-10)

- **"This One Equation Powers GPS, Rockets, and Robots"** — [youtu.be/lIYYJMHAwMU](https://www.youtube.com/watch?v=lIYYJMHAwMU)
  Kalman filter intuition video, *user-sourced*. Covers 1-D Gaussian fusion → Kalman gain →
  predict/update. Use for: first-pass intuition only; it hand-waves Q vs R.
- **Roger Labbe — _Kalman and Bayesian Filters in Python_** —
  [github.com/rlabbe/Kalman-and-Bayesian-Filters-in-Python](https://github.com/rlabbe/Kalman-and-Bayesian-Filters-in-Python)
  *High-trust primary source for the estimation thread.* Free, runnable Jupyter notebooks, from 1-D
  fusion through EKF/UKF. Use for: any KF depth beyond intuition; sim prototyping patterns.
- **kalmanfilter.net** — [kalmanfilter.net](https://www.kalmanfilter.net/)
  Equation-by-equation walkthrough with numeric examples. Use for: a second angle on any single KF equation.
- **Mahony et al. 2008 (already cited in `wiki/theory/mahony-filter.md`)** — why the firmware uses a
  fixed-gain SO(3) complementary filter *instead of* a KF for attitude.
- **Ioannou & Sun, _Robust Adaptive Control_** — free PDF from the author's USC page
  ([search "Ioannou Robust Adaptive Control pdf"](https://viterbi-web.usc.edu/~ioannou/Robust_Adaptive_Control.htm)).
  Ch. 4: least-squares adaptive laws — RLS-as-KF with time-varying P as the learning rate, forgetting
  factors, covariance wind-up. Use for: the uncertainty-aware-adaptation thread (γ vs. P), with proofs.
- **Labbe ch. 13 (Smoothing / RTS smoother)** — the recipe for offline cleanup of SysID flight logs
  (non-causal, no phase lag). Use for: `sysid_analysis.py` data-quality upgrade.

## Wisdom (Communities)
*Not yet proposed — will suggest a high-signal control/drone community once you've shipped your first
flag-gated change and have something concrete to get critiqued.*

## Gaps
- No confirmed community yet for firmware-control-law critique (deferred until first flag-gated change ships).
- No papers/codebases logged yet — will add as the mission pulls from them.
