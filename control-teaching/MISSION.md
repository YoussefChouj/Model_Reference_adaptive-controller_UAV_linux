# Mission: Master the drone's control law, then extend it safely

## Why
You are running a real STM32F4 quadrotor firmware with a cascaded-PID + MRAC control
law, and writing a master's thesis on MRAC path tracking. You want to fold worthwhile
techniques into your own firmware — but only after you understand exactly where each one
plugs in and can prove it doesn't regress the flying vehicle. Every new idea ships behind
a flag, default OFF, so the current control law stays the trusted baseline.

Sources are deliberately plural. Brian Douglas's "Understanding PID Control" series is the
*current* input, but not the only one: as this progresses you'll pull from papers, other
codebases, other video series, and textbooks — sometimes to add a feature to the existing
law, sometimes to prototype an entirely new law. The dual purpose is concrete and broad at
once: (1) ship what serves the **thesis** (MRAC path tracking), and (2) grow as a master's
student in control science & engineering into someone who knows the landscape of what's out
there and can judge, adapt, and combine ideas from any source — not just follow one tutorial.

## Success looks like
- You can draw the firmware's control cascade from memory (position → velocity → angle → rate → mixer) and say which loop MRAC augments.
- For any technique from *any* source (video, paper, codebase), you can point to the exact function/line where it would attach in your firmware and name what it replaces or adds.
- You can add a new control feature behind a compile- or runtime flag, keep the old path as default, and test both against each other in the sim before flying.
- You can read `pid.c` / `mrac.c` and explain each anti-windup and clamp mechanism without notes.
- You can read a control paper or a foreign codebase and extract the one transferable idea, judging whether it's worth trying — the mark of a control engineer, not a tutorial-follower.

## Constraints
- Toolchain: Keil uVision V5 / ARMCC V5.06. Firmware is the source of truth; sim (`sim/`) is firmware-parity for offline testing.
- Beginner/intermediate embedded background — build intuition before heavy math.
- Real flying hardware: nothing lands in the default control path untested. Flags default OFF.
- Learning happens across many short sessions; each lesson must stand alone.

## Out of scope (for now)
- Rewriting the estimator (SINS/optical flow) or motor mixer from scratch.
- The thesis's NN path-tracking layer — that sits above the control law, not inside it.

Note: entirely new control laws (LQR/MPC/state-space, or new adaptive schemes) are *not*
permanently out of scope — they're future prototypes the mission explicitly allows. They're
just deferred until the incremental, flag-gated work on the existing PID+MRAC law is solid.
When we go there, it starts as a sim prototype, never a direct firmware swap.
