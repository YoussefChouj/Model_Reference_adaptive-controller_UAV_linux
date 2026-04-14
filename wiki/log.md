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
