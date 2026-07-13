# Wiki Log

## [2026-04-13] init | Wiki initialized with Karpathy LLM Wiki pattern
- Created wiki structure: concepts/, entities/, sources/, queries/
- Created raw structure: papers/, notes/, web/, transcripts/
- Seeded from docs/decisions.md and docs/interfaces.md

## [2026-04-13] ingest | Architectural Decisions
- Created: concepts/multi-rate-task-partitioning.md
- Created: concepts/ground-station-binary-protocol.md
- Created: concepts/virtual-rc-authority.md
- Created: concepts/path-arbitration.md
- Created: sources/architectural-decisions.md

## [2026-04-13] ingest | Cross-Subsystem Interfaces
- Created: concepts/control-loop-timing.md
- Created: entities/stabilizer-task.md
- Created: entities/autofly-task.md
- Created: entities/imu-update.md
- Created: entities/ground-station-bridge.md
- Created: entities/motor-mixer.md
- Created: sources/cross-subsystem-interfaces.md

## [2026-04-14] enrich | Wiki Gap Plan — Phase 1 & 2
- Enriched all 10 existing entity and concept pages with code anchors, signatures, and Evidence vs Inference sections
- Created: concepts/mrac-control-law.md
- Created: concepts/sdk-arming-state-machine.md
- Created: concepts/autonomous-path-generation.md
- Created: entities/dashboard.md
- Created: entities/flight-logger.md
- Created: entities/vofa-streaming.md
- Created: entities/flash-memory.md
- Created: entities/timer-pwm-config.md

## [2026-04-14] enrich | Source-of-Truth Pass — 12 new pages
- Created: quickstart.md (Agent & Developer Quick-Start Guide)
- Created: entities/data-dictionary.md (all shared structs from robot_types.h + global_declare.h)
- Created: entities/pid-controller.md (PID algorithm, anti-windup, yaw wrapping, locx/locy rotation)
- Created: entities/remoter-task.md (RC input, SBUS loss, arming gestures, fly mode)
- Created: concepts/uart-peripheral-map.md (USART1-6 purpose, pins, baud, DMA, ISR mapping)
- Created: concepts/interrupt-map.md (all ISRs, DMA handlers, data flow ISR→task)
- Created: concepts/coordinate-conventions.md (signs for sticks, motors, body/world frame, PWM)
- Created: concepts/tuning-workflow.md (step-by-step PID/MRAC tuning guide)
- Created: concepts/adding-a-command.md (end-to-end recipe for new CMD IDs)
- Created: entities/ground-station-tooling.md (deep_analysis, experiment_db, diag_telemetry_link)
- Created: concepts/config-reference.md (config.yaml keys documented)
- Created: concepts/common-pitfalls.md (troubleshooting guide)
- Enriched: overview.md (full architecture diagram, task table, file map, subsystem index)
- Updated: index.md (reorganized with categories, 30 pages indexed)

## [2026-04-14] enrich | External Knowledge Enrichment — 6 new theory/reference pages
- Created: theory/mahony-filter.md (Mahony 2008 SO(3) observer → imu_update.c variable mapping)
- Created: theory/mrac-theory.md (Yucelen papers → mrac.h/mrac_math.c architecture mapping)
- Created: theory/cascaded-pid.md (Cascade design rules, tuning order, anti-windup → pid.c/StabilizerTask.c)
- Created: theory/yucelen-lectures.md (Digest of key lectures with code cross-references)
- Created: reference/stm32f4-peripherals.md (Used-only peripherals: TIM3/TIM5, USART+DMA, SPI, NVIC)
- Created: reference/freertos-used.md (Used primitives + deliberate omissions and their consequences)
- Updated: index.md (added Theory and Reference sections, 36 pages total)

## [2026-04-14] ingest | Adaptive control simulation notebooks (external)
- Created: concepts/adaptive-control-simulations.md
- Created: sources/direct-mrac-ff-projection-simulation-notebook.md
- Created: sources/adaptive-control-tutorial-notebook.md
- Created: sources/adaptive-control-tutorial-2-notebook.md
- Updated: index.md (added simulation concept page and 3 notebook source pages)
- Notes: notebook code treated as validated baseline; markdown explanations marked as lower-confidence guidance

## [2026-04-14] enrich | Simulation docs deepening (theory + diagrams + implementation)
- Expanded: concepts/adaptive-control-simulations.md with control-loop, implementation, and experiment-loop diagrams
- Created: concepts/adaptive-simulation-theory-to-code-deep-dive.md
- Expanded: sources/direct-mrac-ff-projection-simulation-notebook.md with end-to-end architecture diagram and theory-to-code mapping
- Updated: index.md (added deep-dive concept entry)

## [2026-07-09] ingest | Motion Planning in Dynamic Environments Survey (grabbed via Discord digest)
- Pulled from server wiki_inbox → raw/papers/2026-07-09-motion-planning-in-dynamic-environments-a-survey-from-classi.md
- Created: literature/openalex-W7163597202.md (raw page-cited grab briefing, parity with server summary)
- Created: sources/motion-planning-dynamic-environments-survey.md (comprehensive beginner-level source page: mental model, taxonomy, jargon decoder, thesis positioning, user's Discord notes)
- Created: concepts/motion-planning-methods.md (planning taxonomy: sampling-based/reactive/learning-based + MPC)
- Created: concepts/conformal-prediction.md (stub — calibrated uncertainty bounds)
- Created: concepts/sim-to-real-gap.md (stub — thesis-central; digital twin + MRAC synergy)
- Updated: index.md (new "Research & Thesis Background" concept section; new "Literature" section — also indexed previously-orphaned literature/arxiv-2603.18584.md)
- Convention note: first ingest using the comprehensive beginner-level digestion convention (jargon glossary + prerequisite primer + concept stubs per grabbed paper)
