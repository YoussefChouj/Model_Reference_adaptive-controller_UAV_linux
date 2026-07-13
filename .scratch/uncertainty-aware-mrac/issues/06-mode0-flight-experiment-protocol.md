# Real-drone experiment protocol on MRAC mode 0

Type: grilling
Status: open
Blocked by: 04

## Question

Define the flight-test protocol for the chosen mechanism on MRAC mode 0 (passthrough, empirically-tuned PID as reference-error generator): metrics and ranking (reuse ADR-0002 ranking / `analyze-results` pipeline?), ON-vs-OFF flag discipline per flight, safety gates (note SysID deferred aborts — battery-low, OF-stale, saturation — are still unimplemented; do they block these flights?), and abort criteria specific to adaptation-rate changes (e.g., weight-divergence watch).
