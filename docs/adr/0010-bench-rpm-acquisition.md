# 0010 - Bench RPM acquisition (EXTI on repurposed TIM2 pins)

*   **Status:** Accepted (design 2026-07-05; implementation delegated to Cursor agent —
    contract `.agent_contracts/TASK_20260705_rpm_bench_acquisition.md`)
*   **Date:** 2026-07-05
*   **Depends on:** ADR-0009 (motor bench-test mode), `docs/bench_characterization.md`

## Context

The thrust-stand sweep (ADR-0009) logs `(CCR, thrust, voltage)` but not ω, so the
professor's `T = k·ω²` model can only be validated by *assuming* a CCR→ω map. Adding
measured RPM per logged point closes that loop and gives the sim's actuator stage its
`CCR → ω → T` chain directly.

Sensor selection already happened upstream: ESC telemetry is unavailable (classic
PWM ESCs), a motor phase-tap was rejected as too invasive for now, and the E18-D80NK
reflective sensor was rejected because its ~2 ms response misses marks at flight RPM.
Chosen: **TCRT5000 + LM393 modules** (¥3, 3-wire, 1–25 mm range, µs-scale response,
output active-HIGH on reflection), **two reflective marks per prop** (one per blade
underside at the root, sensor looking up from below, clear of the prop disc).

## Decision

### 1. Pins: repurpose the four TIM2 "spare PWM" pins as EXTI inputs

`PWM_TIM2_Init` configures PA5/PB3/PB10/PB11 as TIM2 PWM outputs that **nothing ever
writes** — they are broken out on the same 3-pin header type as the motors. We stop
calling `PWM_TIM2_Init` in `BSP_Init` and initialize the same four pins as EXTI
rising-edge inputs with pull-downs (`BSP/rpm.c`). The dead init function stays in
`pwm.c` untouched (surgical change; trivially revertible by swapping the call back).

Distinct EXTI line indices (5, 3, 10, 11) — no line conflicts; no application EXTI
existed before. Vectors: EXTI3, EXTI9_5, EXTI15_10.

*   **Why not TIM input capture?** The pins land on TIM2 channels, but input capture
    buys accuracy we don't need (DWT timestamping already gives ~6 ns resolution on a
    ~20 ms period) and costs a shared-timer configuration tangle. EXTI + DWT is smaller.
*   **PA5 caveat:** PA5 is not 5V-tolerant (ADC/DAC-class). If the header rail measures
    5 V, the module output swings 5 V. Bench rule: use the PB3/PB10/PB11 headers (one
    motor is tested at a time); PA5 gets a 10k series resistor in its jumper wire
    before any 4-sensor in-flight use. If the rail measures 3.3 V, no issue (the LM393
    module works at 3.3 V with reduced IR range — fine at ~10 mm).

### 2. Measurement: per-revolution period via DWT cycle counter

ISR counts rising edges; every **2nd** edge (= one full revolution with 2 marks) it
stores `DWT->CYCCNT` deltas in a 4-deep ring. `RPM_Get` averages the ring →
`RPM = 60·f_cpu/period`, with a 0.5 s staleness timeout → 0 and a >20000 RPM glitch
reject.

*   **Why period, not count-over-gate?** Per-revolution resolution and instant
    response; the user wants the best data and has purpose-made reflective tape
    (clean edges).
*   **Why time every 2nd edge?** The two marks are never exactly 180° apart, so
    edge-to-edge intervals alternate short/long. Mark-A-to-mark-A timing cancels the
    placement asymmetry exactly; the ring average then only smooths true jitter.
*   ISRs contain no floats and no FreeRTOS calls (priority-agnostic under
    `NVIC_PriorityGroup_4`).

### 3. Telemetry: extend frame 0x04, proto v7 → v8

Append 4× u16 RPM to the bench frame (12 → 20 B payload, layout `<I B H f B 4H`).
Same dual-length backward-compat pattern as Frame B v2/v3: the GS accepts both sizes.
Dashboard shows live RPM, and **Log point** rows gain `rpm1..4, rpm (max), t_est_N`
where `t_est_N = k·(ω_measured)²` from the existing propeller-model `k` field —
model-vs-scale error is visible per logged point.

*   **Why in 0x04, not a new frame?** RPM is only meaningful alongside CCR/voltage;
    one frame keeps the CSV row atomic and the parser surface small.

## Consequences

*   `GS_PROTO_VERSION` 8. Sync: `serial_bridge.py`, `frame_simulator.py`,
    `diag_telemetry_link.py`, `docs/channel_map.txt`.
*   Channel numbering is **sensor-socket** numbering, not motor numbering — the
    physical plugging (which header the one bench sensor uses) decides the pairing;
    the dashboard's `rpm = max(rpm1..4)` sidesteps it on the bench.
*   In-flight 4-motor RPM becomes possible later (EEPROM-less MRAC persistence and
    per-motor health checks are candidate consumers) but is **out of scope** here:
    no flight-path code consumes `RPM_Get` yet.
*   The bifilar-pendulum inertia experiment (bench_characterization.md §1) needs
    **none of this** — it rides existing Frame B gyro telemetry at 20 Hz (analysis
    contract `.agent_contracts/TASK_20260705_inertia_analysis.md`).
