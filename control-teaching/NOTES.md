# Teaching Notes

## About the learner
- Master's thesis on MRAC path tracking; runs real STM32F4 quadrotor firmware (Keil uVision V5 / ARMCC V5.06).
- Beginner/intermediate embedded — build intuition before math.
- Firmware is the source of truth; `sim/` is a firmware-parity offline test bed (44 tests green).

## How they want to be taught
- Learning by folding a YouTube PID series into their own firmware, one technique per session.
- Non-negotiable: every addition ships behind a flag, **default OFF = today's behaviour**, testable ON-vs-OFF in `sim/` before flying.
- Wants to know the exact function/line where each technique attaches.

## Workspace conventions
- Workspace lives in `control-teaching/` (kept out of firmware repo root to avoid clutter).
- Firmware naming trap to repeat often: `gyrox` = ROLL rate, `gyroy` = PITCH rate.
- Lessons are self-contained HTML in `lessons/`, shared styles in `assets/lesson.css`.

## Open threads
- Anti-windup thread: sim/ RatePID A/B (ON-vs-OFF) for AW_CLAMP/AW_BACKCALC still pending — **must run before flying** (see record 0003).
- Estimation thread opened 2026-07-10 (Lesson 4, Kalman filter). Watch for the Q-vs-R confusion resurfacing (record 0004).
- **User pulled the estimation thread toward the mission (2026-07-10):** wants (a) KF/smoothing to clean SysID flight data offline, (b) uncertainty-aware adaptation. Taught the bridge: RLS = KF on parameters; its P = per-parameter time-varying learning rate vs. firmware's fixed γ — same fixed-vs-computed-gain story as Mahony vs. Kₖ. Candidate lessons: RTS smoother for `sysid_analysis.py`; RLS-vs-gradient A/B in `sim/` (needs forgetting factor / covariance bounds — PE dragon). Labbe priority raised to ch. 1–7 + ch. 13.
- Quiz widget now shared at `assets/quiz.js`; lessons 1–3 keep their inline copies (don't churn them). New lessons use the asset.
- User has started self-sourcing material (KF video) — lessons can now respond to what they bring, not just the PID series order.
