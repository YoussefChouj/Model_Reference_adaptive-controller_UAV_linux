# SINDy flight manifests

This directory defines named variable sets for SINDy telemetry logging.
The manifests are used by `stream_log.py` to subscribe to the right firmware
variables at the right rates.

---

## How to use

Edit `ground_station/livewatch/log_frames.md` (the runtime frame definition)
or `ground_station/livewatch/manifests.yaml` (the named manifest store) to
add the variables you need, then run:

```bash
python -m ground_station.livewatch.stream_log \
  --group "80:mrac_state.roll.e,mrac_state.roll.u_nom,mrac_state.roll.u_ad,mrac_state.roll.xm,mrac_state.roll.Theta:6" \
  --group "80:mrac_state.pitch.e,mrac_state.pitch.u_nom,mrac_state.pitch.u_ad,mrac_state.pitch.xm,mrac_state.pitch.Theta:6" \
  --group "80:mrac_state.yaw.e,mrac_state.yaw.u_nom,mrac_state.yaw.u_ad,mrac_state.yaw.xm,mrac_state.yaw.Theta:6" \
  --seconds 60 --out my_flight.csv
```

---

## Manifest: sindy_adaptive_law

For SINDy on the adaptive law (prior-13).

Logs MRAC signals at 80 Hz — the maximum achievable rate — so the
time derivatives are as accurate as possible.

```
Slot 0 @ 80 Hz:  mrac_state.roll.e, mrac_state.roll.u_nom,
                 mrac_state.roll.u_ad, mrac_state.roll.xm,
                 mrac_state.roll.Theta:6
Slot 1 @ 80 Hz:  (pitch — same fields)
Slot 2 @ 80 Hz:  (yaw — same fields)
Slot 3 @ 80 Hz:  (z — same fields)
```

**Budget check** (UART5 2304 B/s budget, real ceiling ~1600 B/s):
- 4 slots × 6 × 4 B × 80 Hz / 80.4 ≈ 958 B/s → ✅ within budget
- Over USART3 (90 KB/s): 4 × 6 × 4 × 80 / 80.4 ≈ 958 B/s → ✅

**When to use:**
- After a flight segment where the adaptive law has converged (Θ drift < 5 %)
- For a scenario you want to seed with a prior

---

## Manifest: sindy_plant

For SINDy on plant dynamics (prior-13b).

Logs rate setpoints and measured rates at 80 Hz to identify
`d(rate)/dt = f(rate, command)`.

```
Slot 0 @ 80 Hz:  pid.gyrox.Des, pid.gyrox.FB, pid.gyrox.U
Slot 1 @ 80 Hz:  pid.gyroy.Des, pid.gyroy.FB, pid.gyroy.U
Slot 2 @ 80 Hz:  pid.gyroz.Des, pid.gyroz.FB, pid.gyroz.U
```

**Note:** `U` is the PID output after mixing, not the raw motor PWM.
For raw motor mapping, use `actuator_outputs` if your firmware exposes it.

---

## Manifest: sindy_combined

Both the adaptive-law signals and the plant-dynamics signals, at 40 Hz
(to stay within the UART5 budget).

```
Slot 0 @ 40 Hz:  mrac_state.roll.e, mrac_state.roll.u_nom,
                  mrac_state.roll.u_ad, mrac_state.roll.xm,
                  mrac_state.roll.Theta:6,
                  pid.gyrox.Des, pid.gyrox.FB
Slot 1 @ 40 Hz:  (pitch — same fields)
Slot 2 @ 40 Hz:  (yaw — same fields)
```

**When to use:**
- You want both SINDy on adaptive law AND SINDy on plant from one flight
- You can afford 40 Hz (not enough for the 80 Hz you want, but the minimum
  for meaningful derivative estimation)
