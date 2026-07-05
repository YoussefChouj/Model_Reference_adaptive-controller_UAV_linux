# 0009 - Motor bench-test mode (thrust-stand experiment)

*   **Status:** Accepted (firmware + ground station implemented 2026-06-24; sim ingestion pending)
*   **Date:** 2026-06-24
*   **Depends on:** protocol contract (`Global_file/global_declare.h` `GS_PROTO_VERSION`), bench guide (`docs/bench_characterization.md`)

## Context

The sim plant is an identified linear rate model + pure transport delay; it has **no
actuator dynamics, no thrust curve, and no battery-sag model** (see the Phase-1 findings
and the planned `PlantStage` pipeline). The single highest-value way to close that gap is
a bench thrust-stand sweep: drive one motor at a known CCR, read thrust off a kitchen
scale, and record pack voltage — producing the `CCR → thrust` curve, the
`thrust = f(CCR, V)` surface, and the data to validate the professor's approximate
`T = k·ω²` model. This needs a way to drive **one** motor at a **commanded CCR** from the
dashboard, off the flight control path. The flight firmware only ever drives all four
motors through the mixer (`Update_Motor` → `Set_PWM_Motors`); there was no single-motor
bench path.

## Decision

Add a dedicated **motor bench-test mode**: CMD `0x16` to command it, telemetry frame
`0x04` to observe it, and an override branch at the top of `Update_Motor` to drive it.

### 1. Command — CMD 0x16 (idx/val)

*   idx 0 = enable / **heartbeat** (val ≥ 0.5 ON; every send pets the dead-man)
*   idx 1 = motor select (1..4 = M1..M4; 0 = none)
*   idx 2 = commanded CCR (firmware clamps to `[2000, 4000]`)

### 2. Actuator override (`StabilizerTask.c` `Update_Motor`)

A branch at the **top** of `Update_Motor` (before the FSM): if `motor_test_active`, drive
**only the selected channel** to `motor_test_ccr` (others held at `Motor_PWM_ZERO`) via
`Set_PWM_Motors()` (which applies the `[2000,4000]` clamp), then `return`. Fully isolated
from flight logic.

### 3. Telemetry — frame 0x04 @100 Hz

While `motor_test_active`, frame `0x04` **replaces A/B** (same pattern as the 0x03 SysID
frame). Payload (12 B): `u32 sample_counter, u8 motor_id, u16 commanded_ccr, f real_voltage,
u8 active`. `Get_Voltage()` is called **in the frame builder** so voltage is fresh per
frame — `SystemMonitor_Task` only refreshes `real_voltage` at 1 Hz, too slow to catch pack
sag during a sweep. 100 Hz (the base telemetry rate) was chosen over 20/50 Hz: the frame is
tiny, the link has margin, and it captures CCR-step settling and voltage sag with headroom.

## Safety model (the load-bearing part)

Driving a bare motor from a GUI is dangerous, so the guards are layered:

*   **DISARMED-only.** The override refuses to run unless `FlightFSM_GetState() ==
    DISARMED`; any transition out of DISARMED clears `motor_test_active` and zeroes motors.
*   **Dead-man.** The stabilizer (200 Hz) increments `motor_test_watchdog` each tick; the
    CMD 0x16 heartbeat resets it. If no heartbeat arrives within
    `MOTOR_TEST_DEADMAN_TICKS = 100` (500 ms) the motor is zeroed and test mode exits. The
    dashboard sends the heartbeat every ~150 ms from its render loop.
*   **CCR cap with explicit consent.** Full range to 4000 is allowed (needed for the whole
    thrust curve), but the dashboard clamps CCR to 3000 unless the operator ticks
    "Allow high power (CCR > 3000)".
*   **RC / arming remains the final authority** — unchanged.

`DEFAULT` flight behaviour is byte-identical: the override is skipped whenever
`motor_test_active == 0`.

## Consequences

*   **Protocol bump `GS_PROTO_VERSION` 6 → 7** (`global_declare.h` and
    `serial_bridge.py` must match). New CMD 0x16 and frame 0x04 are additive.
*   The ground station gained a **Motor Bench tab** (`dashboard.py`): motor select, fixed
    CCR-step buttons (even coverage of the `T ~ CCR²` curve), high-power gate, START/STOP,
    live voltage/CCR readout, a propeller-model panel (`k, a, b`), and manual thrust-point
    logging to `logs/bench/thrust_<ts>.csv` (each step click and START/STOP is logged too,
    so manual scale readings align to settled segments).
*   **Not done:** sim ingestion — the `PlantStage` actuator + battery stages that consume
    this data (planned ADR for the sim stage pipeline). The motor time constant (actuator
    lag) is **not** captured by manual scale logging; it needs the auto-stand (load cell +
    HX711) from `bench_characterization.md §2b` or closed-loop flight-log identification.
