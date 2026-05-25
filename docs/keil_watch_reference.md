# Keil5 Watch Window — Quick Reference

Copy-paste these expressions directly into the Keil5 Watch window.

---

## Flight State / Arming

```
DroneStatus.FlyMode
DroneStatus.Armed
drone_mode
sbus_lost
sbus_last_valid_tick
GS_KeySDKflag
bench_mode_active
```

`drone_mode`: 0=IDLE, 1=FLY, 2=LAND  
`DroneStatus.FlyMode`: 0=DangerousStop, 1=SDK

---

## RC / SBUS

```
sbus_channel[0]
sbus_channel[1]
sbus_channel[2]
sbus_channel[3]
sbus_channel[4]
sbus_channel[7]
sbus_channel[9]
Remoter.RolCtrler
Remoter.PitCtrler
Remoter.ThrCtrler
Remoter.YawCtrler
```

| Index | Channel | Function |
|-------|---------|----------|
| [0] | ch1 | Roll |
| [1] | ch2 | Pitch |
| [2] | ch3 | Throttle |
| [3] | ch4 | Yaw |
| [4] | ch5 | Mode switch (low≈300/mid≈1000/high≈1600) |
| [7] | ch8 | Preset path trigger |
| [9] | ch10 | Kill switch (≤500 = STOP) |

---

## TWC / Waypoint

```
TWC.execute
TWC.target_x
TWC.target_y
TWC.target_z
TWC.set_yaw
TWC.world_x
TWC.world_y
TWC.world_z
TWC.real_yaw
TWC_arrived
sbus_path_trigger
```

**Units:** `target_x/y` in **cm**, `target_z` in **metres**.

---

## Attitude PIDs (inner loop)

```
Ctrler.pitchPID.FB
Ctrler.pitchPID.Des
Ctrler.pitchPID.U
Ctrler.rollPID.FB
Ctrler.rollPID.Des
Ctrler.rollPID.U
Ctrler.yawPID.FB
Ctrler.yawPID.Des
Ctrler.yawPID.U
```

---

## Rate PIDs

```
Ctrler.gyroxPID.FB
Ctrler.gyroxPID.Des
Ctrler.gyroxPID.U
Ctrler.gyroyPID.FB
Ctrler.gyroyPID.Des
Ctrler.gyroyPID.U
Ctrler.gyrozPID.FB
Ctrler.gyrozPID.Des
Ctrler.gyrozPID.U
```

---

## Altitude PIDs

```
Ctrler.Z_posPID.FB
Ctrler.Z_posPID.Des
Ctrler.Z_posPID.U
Ctrler.Z_ratePID.FB
Ctrler.Z_ratePID.Des
Ctrler.Z_ratePID.U
```

**Units:** metres.

---

## Position PIDs (optical flow / XY)

```
Ctrler.locxPID.FB
Ctrler.locxPID.Des
Ctrler.locxPID.U
Ctrler.locyPID.FB
Ctrler.locyPID.Des
Ctrler.locyPID.U
```

**Units:** **centimetres**. Divide by 100 to get metres.

---

## Motor Outputs

```
mymotor.motor1
mymotor.motor2
mymotor.motor3
mymotor.motor4
```

---

## Safety Limits (set from GS)

```
gs_max_horizontal_speed_mps
gs_max_vertical_speed_mps
gs_max_pitch_deg
gs_max_roll_deg
gs_throttle_min_pct
gs_throttle_max_pct
```

---

## Path Modes

```
sinusoid_path.active
sinusoid_path.center_x
sinusoid_path.center_y
sinusoid_path.center_z
sinusoid_path.amplitude
sinusoid_path.frequency
sinusoid_path.t_elapsed
circle_path.active
circle_path.center_x
circle_path.center_y
circle_path.center_z
circle_path.radius
circle_path.angular_speed
circle_path.theta
circle_path.t_elapsed
```

---

## System Monitor / Comms

```
system_monitor.USART4_task_cnt
system_monitor.USART5_task_cnt
system_monitor.task_cnt
```

Increment `USART4/5_task_cnt` once per received frame — use to confirm commands are arriving.
