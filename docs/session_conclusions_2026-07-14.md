# Session conclusions — 2026-07-14

OF angle-mode escape, real-flight drift diagnosis, and RPM-sensor bring-up.
Deeper detail for the OF/alt items lives in `docs/tracking_baseline_and_drift.md` (v5 entry).

---

## 1. Firmware changes made this session (REFLASH needed to apply)

All in `TASK/StabilizerTask.c` unless noted. Proto bumped **v10 → v11**.

| Change | Where | What |
|---|---|---|
| **Angle-mode escape** | `case_Update_pitrol_Des` | New switch **ch6 `OFHOLD_CH = sbus_channel[5]`** (your switch: low ~306 / high ~1694). **LOW or signal-lost = ANGLE MODE (default)**: sticks command a body-frame lean angle directly, OF loops (position AND velocity) fully bypassed, centered = level. HIGH = OF position-hold (old behaviour). Boot/failsafe default = angle mode, so it never lifts off into OF hold. |
| **Alt gate hardened** | `Update_Data`, `of2_raw_h` | Floor 0.5→5 cm (rejects 1 cm dropouts), + 0.10 m/tick jump limit with 20-tick (100 ms) forced resync. `<500 cm` already rejected 0xFFFF/65535. |
| **OF bias cal (v4, prior turn)** | `Update_Data` position block | Calibration now runs whenever `of_quality >= 50`, **not armed-only**; integration frozen on lock loss. |
| **`status.of_hold` telemetry** | `send_data.c` Frame 0x01 + `serial_bridge.py` | 1 byte appended before proto_version; payload 39→40 B; proto v11. Logs which mode a flight was in. |
| **RPM debug counters** | `BSP/rpm.c/.h` | `rpm_dbg_edges[4]` (monotonic per-edge count) + `rpm_dbg_period_cyc[4]` (last accepted period, cycles) for Keil watch. |

**Two coordination notes:** (a) reflash firmware AND restart the dashboard together (proto v11 both sides, else Frame A is dropped — that already happened in `flight_1783996082.csv`, which logged Frame-B-only). (b) `frame_simulator.py` is pre-existing-stale (missing `rc_authority`) — left untouched.

---

## 2. Flight behaviour conclusions

- **OF position-hold is unstable in free flight.** Real-flight logs (`flight_1783948890/949038.csv`): on takeoff `locy.FB` ran away 0 → −2.06 m in 1.6 s (accelerating = positive feedback), `roll/pitch.Des` saturated ±15°. Compounded by garbage `of_alt_cm` (1 cm and 0xFFFF=65535) saturating the z-rate loop. The terminal +40° pitch / yaw-spin was the **post-disarm fall**, NOT a mid-air motor failure (pilot disarmed before impact).
- **Root architectural gap:** every mode — even deflected sticks — routed through the OF velocity loop; there was no way to fly without OF. The **angle-mode switch fixes this.**
- **Angle mode works** (`flight_1783996082/996626.csv`): no runaway, attitude tracks the level command. Residual = a **steady ~3° pitch trim** the P-dominant loop can't null → constant horizontal accel → slow drift toward the motor-guard side, which the pilot corrects/disarms.

---

## 3. The real problem to fix next — pitch trim (~3°), three stacking causes

Confirmed on a **level surface, disarmed, motors off** (`flight_1783998534/998842.csv`, both identical):
`pitch.FB = +1.29°`, `roll.FB ≈ 0`.

| Source | Amount | Evidence |
|---|---|---|
| IMU pitch calibration bias | **+1.3°** | level surface reads +1.29° (roll ok) — *but* legs are crash-bent so this could partly be the drone resting nose-up; rotate-180° on the surface to disambiguate (stays +1.3° = IMU; flips to −1.3° = tilted rest) |
| Pitch stick not centered | **+0.8°** | angle-mode `pitch.Des` = +0.81° with "centered" stick |
| CG / thrust imbalance (missing guard) | **~+1.4°** | flight hover held +3.5° = 1.3 + 0.8 + 1.4; the extra ~1.4° only appears under motor load |

**Key context from pilot:** the drone **flew fine before the sensor swap even with the same asymmetry** → the in-air regression correlates with the sensor replacement (IMU remount/bias or added wiring), not the pre-existing imbalance. Rebalancing is deferred (no spare guards/counterweights).

**Recommended fix order (next session):** (1) redo accel/level calibration → removes ~1.3°; (2) trim pitch-stick center on the TX → removes ~0.8°; (3) CG rebalance later → removes ~1.4°; (4) optional: add integral to the pitch *angle* loop to null residual constant torque.

---

## 4. "Desired snaps to FB on arm" — intentional, NOT a bug

Position/altitude/heading loops **latch their setpoint to the current measurement whenever sticks are centered** (`case_Update_loc_Des`, `case_Update_yaw_Des`, Z-hold at `StabilizerTask.c:617`). Confirmed: `locx.Des`↔`locx.FB` corr 0.97, `z_pos.Des`↔`z_pos.FB` corr 1.00. It means "hold current spot/height/heading." Attitude Des (pitch/roll) does NOT snap — it comes from sticks.

---

## 5. RPM sensors — CONCLUSION: firmware is 100% correct; the fault is electrical (sensor side)

**Firmware audit — all pass:**
- Driver `BSP/rpm.c`: EXTI rising-edge on PA5/PB3/PB10/PB11, DWT-timed, 2 pulses/rev, glitch (>20000 RPM) + 0.5 s stale reject, u64 RPM math.
- `RPM_Init()` called first in `BSP.c:9`; ISRs in `stm32f4xx_it.c` route EXTI3/9_5/15_10 → `RPM_EdgeISR(0..3)` and clear pending bits.
- **No conflicts:** USART3=PC10/11, IMU SPI2=PB13/PC2/PC3/PC4/PC5, motors=TIM3/TIM4. `PWM_TIM2_Init()` (which would grab these pins) is **dead code, never called**. Nothing reconfigures these EXTI lines after init.
- **Proven live in Keil:** EXTI `IMR=RTSR=0xC28` (lines 3,5,10,11 unmasked, rising). SWIER software-trigger → `rpm_dbg_edges[2]` incremented → full EXTI→NVIC→ISR path works. `GPIOA MODER` showed PA5 still = input after boot.

**But `rpm_dbg_edges[0..3]` all stayed 0 while waving a mark → no physical rising edges arrive.** So the sensors aren't outputting. All four die together, a few seconds into boot (right after the ~4 s of `delay_ms` in `BSP_Init`, when the IMU/telemetry-radio/motor outputs switch on). **Leading hypothesis: shared 5 V rail sags under the FC's startup load → sensors brown out** (their own detection LED goes dark). Pilot is skeptical of this — UNRESOLVED, parked.

**Wiring facts / cautions for when RPM is revisited:**
- Sensors plug into the **TIM2 header** (`CH2 CH4 CH3 CH1 5v Gnd`). Map: **CH1=PA5=rpm0, CH2=PB3=rpm1, CH3=PB10=rpm2, CH4=PB11=rpm3**.
- ⚠️ **PA5 (CH1) is NOT 5 V-tolerant** (ADC/DAC-class, ~3.6 V max). A 5 V sensor OUT can damage it. Use **CH2/CH3/CH4 (PB3/PB10/PB11, 5 V-tolerant)** or a 10 kΩ series resistor / 3.3 V supply. PB3 is also JTDO → use SWD (not JTAG) when debugging.
- Firmware assumes **2 reflective marks per prop** (`RPM_PULSES_PER_REV=2`); 1 mark → reads half.
- RPM is streamed **only in motor bench-test mode** (0x04 frame, CMD 0x16, disarmed, one motor at a time); NOT in normal-flight A/B. In-flight 4-motor RPM would need adding it to Frame A/B.
- Next physical test proposed: power one sensor from FC TIM2 5v/Gnd (clean rail + common ground), OUT→CH3, watch its LED + `rpm_dbg_edges[2]` through boot.

---

## 6. Immediate next steps

1. **Reflash v11 firmware + restart dashboard** so `status.of_hold` and Frame A log.
2. **Fix the drift** (Section 3): accel/level recal, then pitch-stick trim; re-read `pitch.FB` on a level surface (should → ~0); one low/tethered angle-mode confirmation hover.
3. RPM: resolve sensor power (common ground / stiff 5 V) when convenient — firmware side is done.
