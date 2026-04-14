---
title: Adding a Command
type: concept
tags: [protocol, recipe, firmware, ground-station]
created: 2026-04-14
updated: 2026-04-14
sources: [TASK/send_data.c, BSP/usart4.c, BSP/usart5.c, ground_station/comm/serial_bridge.py, ground_station/gui/dashboard.py]
---

This page is a step-by-step recipe for adding a new ground station command (CMD ID) end-to-end. Follow every step to avoid protocol mismatches between firmware and host.

## Overview

A command is a 9-byte frame: `[0xCC][0xDD][CMD_ID][INDEX][float32 LE][CRC8_XOR]`. See [[Ground-Station Binary Protocol]] for full format.

Current CMD IDs `0x01`-`0x0E` are in use (`TASK/send_data.c:471-673`). The next available IDs are `0x0F` and `0x10` (reserved/unimplemented in current dispatcher).

## Step 1: Define the Command Semantics

Before coding, decide:
- **CMD ID**: next unused (e.g., `0x0F`)
- **Index values**: what does each index mean? (e.g., `idx 0` = param A, `idx 1` = param B)
- **Value type**: always float32, but define the range and units
- **Target global**: which variable(s) does this command write?

## Step 2: Firmware — Add Handler Branch

In `Process_GroundStation_Command()` (`TASK/send_data.c:471`), add a new `case` in the switch/if chain:

```c
// In TASK/send_data.c, after the existing CMD 0x0E block:
else if (cmd_id == 0x0F) {
    switch (idx) {
        case 0: my_new_param_a = value; break;
        case 1: my_new_param_b = value; break;
    }
}
```

**Checklist**:
- [ ] Declare target globals in `Global_file/global_declare.h` with `extern`
- [ ] Define storage variables in the appropriate `.c` file
- [ ] Add bounds checking / `value_limit` if safety-relevant
- [ ] Verify no index collision with existing CMDs

## Step 3: Firmware — Add Telemetry (Optional)

If the new parameter should be observable, add it to Frame A or Frame B packing in `Send_Groundstation_Telemetry_UART4()` (`TASK/send_data.c:281`):

- Frame A: fixed 37-byte payload (`TASK/send_data.c:295`)
- Frame B: variable length, depends on `MAX_NUM_BASIS` (`TASK/send_data.c:330`)

**If changing payload length**: update the length formula in firmware (`TASK/send_data.c:330-331`) AND the host parser expected length in `serial_bridge.py`.

## Step 4: Host — Add Command Sender

In `ground_station/comm/serial_bridge.py`, no code change is needed for the transport layer — `_pack_command_frame` (`ground_station/comm/serial_bridge.py:897`) already handles arbitrary CMD ID/index/value combinations.

The command is sent by calling:
```python
bridge.send_command(cmd_id=0x0F, index=0, value=42.0)
```

## Step 5: Host — Add Telemetry Parser (If Applicable)

If you added telemetry fields in Step 3, update the unpack functions:

- `_unpack_frame_a()` (`ground_station/comm/serial_bridge.py:455`) for Frame A
- `_unpack_frame_b()` (`ground_station/comm/serial_bridge.py:558`) for Frame B

Add the new field name to the telemetry dictionary so downstream consumers (VOFA, dashboard, logger) can access it.

## Step 6: Host — Add Dashboard UI (Optional)

In `ground_station/gui/dashboard.py`, add UI controls that call `_send_cmd`:

```python
self._send_cmd(0x0F, 0, slider_value)
```

Place controls in the appropriate tab (PID Tuning, MRAC Tuning, Paths, Safety, etc.) based on the command's purpose.

## Step 7: Update Documentation

- [ ] Add the new CMD to the table in [[Ground-Station Binary Protocol]] (CMD IDs section)
- [ ] Update [[Config Reference]] if new config keys are involved
- [ ] Update `docs/interfaces.md` if a new cross-subsystem contract is created
- [ ] Update `docs/decisions.md` if this represents an architectural decision

## Validation Checklist

After implementation:

1. **CRC check**: Send command from dashboard, verify firmware receives correct value (add temporary debug telemetry or use debugger)
2. **Boundary check**: Send edge-case values (0, negative, very large) and verify clamping behavior
3. **Bidirectional**: If telemetry was added, verify VOFA+ or dashboard shows the new field
4. **No regression**: Verify existing commands still work (especially if payload lengths changed)

## Common Mistakes

| Mistake | Consequence | Prevention |
|---------|-------------|------------|
| Wrong CMD ID (collision) | Overwrites unrelated parameter | Check existing CMD table first |
| Forgot CRC update on host | All commands rejected by firmware | Use `_pack_command_frame`, don't hand-build |
| Changed Frame B length without updating host | Parser desync, garbled telemetry | Update both `send_data.c` formula AND `serial_bridge.py` expected length |
| No bounds checking on firmware side | Arbitrary float writes to safety params | Always add `value_limit` for safety-critical values |

## See Also

- [[Ground-Station Binary Protocol]] — frame format and existing CMDs
- [[Ground Station Bridge]] — host-side transport
- [[Dashboard]] — UI command dispatch
