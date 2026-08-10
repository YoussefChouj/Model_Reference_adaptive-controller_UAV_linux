# MicoAir WiFi Link — Telemetry Protocol

**2026-08-10. Replaces com0com-based approach.**

## Physical link

```
Drone FC (USART3 @ 921600) → MicoAir WiFi module → WiFi UDP → PC
```

The MicoAir module bridges UART3 and WiFi transparently:

| Direction | Protocol | Port | Notes |
|---|---|---|---|
| FC → PC (telemetry) | UDP | **14550** | Module pushes; no application-level handshake needed |
| PC → FC (commands) | UART5 VCP | COM6 | `0xCC 0xDD` grammar. CMSIS-DAP dongle shares the probe. |

**PC must join the module's AP** (`MicoAir-XXXX`, `192.168.4.1`). The module does **not**
forward between its AP and the upstream internet — the PC's default route goes out the
phone tether; WiFi stays on the module net.

## The nudge requirement

The module routes its UDP downlink to the **source of the most recent uplink datagram**.
Bind alone receives nothing — the first send from the PC's socket is what aims the stream.

Every script that reads UDP 14550 must send at least one datagram before counting:

```python
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", 14550))
sock.sendto(b"\x00", ("192.168.4.1", 14550))  # nudge — one byte is enough
```

The nudge is harmless on the FC: `USART3->HandleRx` counts the bytes but discards them
(no command parser on USART3).

## Measured capacity

| Metric | Value |
|---|---|
| UART wire | 921600 baud, ~91500 B/s |
| UDP payload | ~90363 B/s |
| Efficiency | **98.8 % of wire** |
| Loss | **0.00 %** (alphabet ladder, `scratchpad/micoair_ladder.py`) |

The module adds ~1 % overhead over the raw wire. This is 55× the UART5 CMSIS-DAP path
(~1600 B/s real ceiling).

## Telemetry frames (FC → PC)

### Frame header

```
Byte 0: 0xAA
Byte 1: 0xBB
Byte 2: frame_type  (0x01 = Frame A, 0x02 = Frame B, 0x03 = SysID, ...)
Byte 3: LEN_hi       (payload length, big-endian uint16)
Byte 4: LEN_lo
Byte 5: MAX_NUM_BASIS  (MRAC basis count)
Bytes 6..(6+LEN-1): payload
Last byte: CRC8_XOR  (XOR of bytes 2..(6+LEN-1))
```

### Frame A (0x01) — 100 Hz, MRAC inner loops + status

Used by VOFA+ JustFloat stream.

```
Offset  Type      Name
0       float32   pitch.e
4       float32   pitch.u_ad
8       float32   roll.e
12      float32   roll.u_ad
16      float32   yaw.e
20      float32   yaw.u_ad
24      float32   z.e
28      float32   z.u_ad
32      uint8     status.arm
33      uint8     status.flymode
34      uint8     status.sbus_lost
35      uint8     status.twc_execute
36      uint8     status.twc_arrived
37      uint8     status.rc_authority  (v2+: PC=1, RC=0)
38      uint8     status.of_hold       (v13+: 1=OF hold, 0=angle)
39      uint8     status.estimator_ready (v13+: 1=converged/armable)
40      uint8     proto_version
```

v10 firmware emits 39-byte payload (no `of_hold`/`estimator_ready`). v13 emits 41.
`socket_bridge.py` accepts both.

### Frame B (0x02) — 20 Hz, MRAC weights + PID + path

Payload size depends on `MAX_NUM_BASIS`. See `TASK/send_data.c`.

### SysID frame (0x03) — 100 Hz, excitation data

Active during MRAC system identification. Replace A/B frames while running.

### OF calibration frame (0x05) — 200 Hz

Active during optical-flow calibration.

## Subscribe protocol (PC → FC)

PC sends a `0xCC 0xDD` **subscribe request** over UART5 to start streaming named
variables. No subscribe over WiFi — UDP 14550 is **receive-only**.

```
0xCC 0xDD [0x21] [slot] [divider] [addr_hi] [addr_lo] [count] [crc8]
```

- `divider = round(80.4 / desired_hz)` — firmware runs at ~80 Hz
- `addr` = DWARF address resolved from `OBJ/JX_FLY.axf`
- Up to **4 slots**, each at its own independent rate
- Firmware replies `0x7F` if total rate exceeds link budget

Firmware `Send_Task` sends existing frames (A/B/SysID/OFCal) regardless of subscriptions.
Subscriptions add **streaming frames** on top.

**`stream_log.py` handles all of this** — it reads `log_frames.md` to get variable names,
resolves addresses from the ELF, and sends subscribe requests automatically:

```bash
# default frame (from log_frames.md)
python -m ground_station.livewatch.stream_log --transport usart3 --seconds 30 --out logs/run.csv

# custom groups at different rates
python -m ground_station.livewatch.stream_log --transport usart3 \
  --group "40:mrac_state.roll.Theta:6" \
  --group "5:imu_data.rol:3" \
  --out logs/custom.csv
```

## Command protocol (PC → FC)

**Commands go over UART5 only** (COM6, CMSIS-DAP VCP). The radio path does not forward them.

```
0xCC 0xDD [CMD] [IDX] [float32 LE] [CRC8_XOR]
```

| CMD | Name | Notes |
|---|---|---|
| 0x01 | PID gains | |
| 0x02 | MRAC gamma | |
| 0x03 | mixer / u_max | |
| 0x04 | flight mode | idx0=DangerousStop+abort, idx1=SDK |
| 0x06 | virtual RC | SBUS lost + SDK authority |
| 0x07 | bench mode | |
| 0x09 | GS safety limits | max_horiz_m/s, max_vert_m/s, max_pitch/roll_deg |
| 0x0A | TWC (point target) | FlyMode_SDK only |
| 0x0B | sinusoid path | FlyMode_SDK only |
| 0x0C | circle path | FlyMode_SDK only |
| 0x0D | abort all paths | |
| 0x0E | arm/disarm | idx0: val≥0.5=arm, <0.5=disarm |
| 0x0F | MRAC flags | adaptation, projection, deadzone, freeze, saturation, ... |
| 0x10 | reset OF origin | |
| 0x14 | abort SysID | |
| 0x17 | capture OF velocity bias | Drone must be level+still |
| 0x18 | force recal | GROUND_IDLE + disarmed only |

Full table: `ground_station/comm/serial_bridge.py` `_pack_command_frame`.

## VOFA+ integration

VOFA+ connects over UDP directly — no com0com, no virtual COM port.

| Stream | Default port | Protocol | Source |
|---|---|---|---|
| A | **1347** | JustFloat (LE float32 × 13 + tail) | Frame A (100 Hz) |
| B | **1348** | JustFloat (LE float32 × N) | Frame B (20 Hz) |

The dashboard's `VofaManager` auto-generates the channel name list from the Frame A / Frame B
unpacking code in `serial_bridge.py` (`_build_frame_a_channel_names`,
`_build_frame_b_channel_names`). Channel names are applied to VOFA's `vofa+.config.json` on
every `open_plot()` call — no manual renaming needed.

VOFA+ is launched and managed by the dashboard (`Dashboard.open_vofa()`). Standalone launch:

```bash
# Frame A on port 1347 — set VOFA+ protocol to "JustFloat", port 1347
# Frame B on port 1348 — second VOFA+ instance, protocol "JustFloat", port 1348
```

## Tools reference

| Tool | Transport | What it does |
|---|---|---|
| `ground_station.livewatch.stream_log --transport usart3` | UDP 14550 | Subscribe + log named variables to CSV |
| `ground_station.livewatch.watch --transport usart3` | UDP 14550 | Live frame display |
| `ground_station.livewatch.log --transport usart3` | UDP 14550 | Continuous CSV capture |
| `ground_station.gui.dashboard` | UART5 + UDP 1347/1348 | Full GUI + VOFA+ plots |
| `scratchpad/micoair_ladder.py` | UDP 14550 | Throughput/quality benchmark |
| `scratchpad/verify_attitude_frame.py` | UDP 14550 | Frame sanity check |

**No com0com.** All tools speak UDP natively. `scratchpad/micoair_vcom_bridge.py` is retired.
