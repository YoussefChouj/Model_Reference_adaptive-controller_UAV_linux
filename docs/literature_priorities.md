---
slug: drone-mrac
updated: 2026-07-02
provenance: distilled from CONTEXT.md, CLAUDE.md session state, docs/ (ADRs, sysid_results), and thesis context
---

# Literature Priorities — FreeRTOS 6-DOF MRAC Adaptive Flight Controller

**One-liner:** A quadrotor flight stack with a per-axis Model Reference Adaptive Controller
(MRAC) inner loop on STM32F4, whose trajectory-tracking performance is the subject of a
master's thesis on NN dense-waypoint path tracking.
**Current phase / goal:** Sim rebuild **Phase 2** — 6-DOF/Gazebo plant, offline Lyapunov
P-matrix derivation for firmware, and larger-mismatch MRAC experiments; in parallel, the
thesis NN path-tracking (behavioral cloning + Transformer) direction.

## Priority topics (ranked by current effort — digest recommends top-down)

| # | Topic | Why it matters *now* | Search terms (feed the APIs verbatim) | Route | "High relevance" = |
|---|-------|----------------------|----------------------------------------|-------|--------------------|
| 1 | MRAC inner-loop adaptive control | Core controller; running larger-mismatch experiments, projection/leakage robustness | `"model reference adaptive control" quadrotor` `"L1 adaptive control" UAV` `projection operator adaptive` `composite adaptation MRAC` `author:Lavretsky` `author:Hovakimyan` | #control-laws | proposes an adaptive law we could implement/compare on a rate loop with mismatch |
| 2 | Reference-model & offline Lyapunov P design | Phase-2 task: derive P offline (`compute_reference_model.py`), set `ref_model_bw` | `Lyapunov reference model design adaptive` `"algebraic Lyapunov equation" reference model` `reference model bandwidth selection adaptive control` | #control-laws | gives a principled P / bandwidth choice tied to closed-loop BW |
| 3 | Closed-loop system identification (UAV inner loop) | SysID excites one axis' rate setpoint; recover lumped J/b + BW from flight data | `closed-loop system identification quadrotor` `multisine frequency sweep UAV identification` `"grey-box" identification rotorcraft inner loop` | #control-laws | a closed-loop excitation/estimation method usable in a ~2 m test cube |
| 4 | Trajectory tracking & reference generation | Thesis metric; figure-8/lemniscate, waypoint-density (Δs) vs tracking | `quadrotor trajectory tracking control` `geometric control SE(3) quadrotor` `minimum snap trajectory generation` `waypoint spacing reference quantization tracking` | #control-laws | improves shape fidelity / cross-track under a staircase reference |
| 5 | Learning-based / NN path tracking (thesis core) | Behavioral cloning from expert pilot, Transformer trajectory net, dense waypoints | `imitation learning quadrotor control` `behavioral cloning UAV path tracking` `transformer trajectory prediction control` `learning-based adaptive control drone` | #research-planning | a BC/transformer control policy for waypoint tracking with data/robustness insight |
| 6 | Sim-to-real / digital twin / 6-DOF Gazebo | Phase-2 plant bring-up; validate adaptive law before hardware | `sim-to-real transfer quadrotor control` `digital twin UAV control validation` `Gazebo quadrotor 6-DOF adaptive control` | #simulation | a sim-to-real workflow/gap analysis for adaptive or learned controllers |
| 7 | Optical-flow drift & VIO position feedback | OF `locx/locy.FB` drifts ~50 cm; limits tight-space geofence + XY tracking | `visual-inertial odometry drift MAV` `optical flow position estimation quadrotor` `T265 VIO indoor drone` | #computer-vision | a drift-mitigation/estimation approach improving indoor XY position |

## Open questions / unsolved problems (sharpest recommendation targets)
- **J vs torque-effectiveness identifiability** — from closed-loop flight data the lumped
  input–output model is identifiable but physical `J` and `mrac_to_mixer` effectiveness are
  coupled; is there an excitation/independent-measurement scheme that separates them? Route: #control-laws
- **Reference-model bandwidth from sysid** — principled mapping identified inner-loop BW →
  `ref_model_bw` (currently 80–90% heuristic). Route: #control-laws
- **Adaptation under larger mismatch** — robustness/leakage/dead-zone tuning so the update
  law stays stable as plant/model mismatch grows. Route: #control-laws
- **BC data efficiency + distribution shift** — dense-waypoint tracking policy from limited
  expert-pilot data without covariate-shift failure. Route: #research-planning
- **Sim-to-real gap for adaptive control** — what transfers from a Gazebo-validated MRAC to
  the STM32 firmware. Route: #simulation

## Exclude-list (already owned / solved — do NOT recommend)
- Intro adaptive-control textbooks (Narendra & Annaswamy; Ioannou & Sun; Åström & Wittenmark) — already the baseline.
- Projection-operator foundations (Lavretsky/Pomet–Praly) — already cited/applied.
- Solved in-repo: additive control sign convention (no sign-flip, `B>0`); structured
  regressor basis (`mrac.c:65-91`); waypoint-density arc-length stepping (CONTEXT.md).

## Seed authors / venues / papers (optional — follow these)
- Authors: Lavretsky, Hovakimyan (L1), Annaswamy · Venues: IEEE TAC, CDC, ACC, ICRA, RA-L, IROS ·
  Anchors: L1 adaptive control; projection-based robust MRAC.

## Relevance rubric (how the agent should rank)
- **high** — directly usable for Phase-2 MRAC/sim work or thesis NN tracking (a method we could implement or benchmark against).
- **medium** — adjacent adaptive/learning control or UAV state estimation context.
- **low** — same field, not the current focus.

## Channel routing map (topic domain -> Discord channel)
| Domain | Channel |
|--------|---------|
| adaptive/robust/MRAC control, trajectory tracking, sysid | #control-laws |
| simulation, sim-to-real, digital twin, Gazebo plant | #simulation |
| ROS / Gazebo bring-up / middleware | #ros-integration |
| perception, optical flow, VIO, computer vision | #computer-vision |
| embedded / STM32 / RTOS | #stm32-firmware |
| learning-based path tracking, surveys, cross-cutting planning | #research-planning |
