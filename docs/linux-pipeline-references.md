# Linux build pipeline — authoritative references

This file collects the primary-source documentation behind each non-obvious
decision in `firmware/` and `ground_station/flashtool_linux/`. When in doubt,
check the source rather than guessing.

---

## 1. Cortex-M4 vector table layout

**Source**: ARM, *Cortex-M4 Devices Generic User Guide*, section 2.3.4 "Vector
table". Confirmed via charleskorn.com (2016-04-17), "A deeper look at the
STM32F4 project template: getting things started".

Key facts:
- The first word at offset 0 of the vector table is loaded into MSP on reset.
  It is the **stack pointer value**, not a label.
- Subsequent words are addresses of exception handlers.
- Layout is the same for every Cortex-M4 part — vendor startup code only
  differs in the IRQ names after the standard 16 system handlers.

**Our application**: vector table's first entry is `.word __StackTop`, where
`__StackTop` is defined in the linker script as a concrete address. A weak
`Default_Handler` (infinite loop) backs every external IRQ so an unexpected
interrupt does not jump to address 0.

---

## 2. GNU ld linker script memory regions

**Source**: GNU `ld` manual, *SECTIONS* / *MEMORY* / *PROVIDE*. Canonical
pattern for `__StackTop` + `__HeapBase`/`__HeapLimit` is the
`_user_heap_stack` block, followed by `.` to advance into stack space. The
`newlib` `_sbrk()` walks `_end..__HeapLimit`; the vector table's first word
points at `__StackTop` (the high water mark).

**Our application**: `firmware/cmake/stm32f407zg.ld` puts `.isr_vector`,
`.text`, `.rodata`, `.ARM.exidx` in FLASH. `.data` uses `> SRAM AT > FLASH`
to keep VMA in RAM and LMA in flash for the `Reset_Handler` copy loop.
`.bss` and `._user_heap_stack` go in SRAM with `(NOLOAD)`. `__StackTop` /
`__HeapBase` / `__HeapLimit` / `_estack` all live in this single section,
so no symbol is defined twice.

---

## 3. pyocd session options

**Source**: pyocd `docs/options.md` (main branch, July 2026). The options we
depend on:

| Option | Value | Why |
|---|---|---|
| `connect_mode` | `attach` | Connect without halting the running core. Other modes (`halt`, `pre-reset`, `under-reset`) all halt. |
| `resume_on_disconnect` | `False` | Don't resume cores on disconnect; leave target state untouched. |
| `reset_type` | `system` | NVIC AIRCR.SYSRESETREQ. Pyocd's default already chooses `system`, but we set it explicitly so a future pyocd default change cannot quietly switch to `core`. |
| `target_override` | `stm32f407zgtx` | Chip-specific target. The generic `cortex_m` fallback target has no real flash algorithm — it pretends to program and reports success without committing bytes. Install the STM32F4xx_DFP pack first: `pyocd pack install stm32f407`. |
| `cmsis_dap.deferred_transfers` | `0` | pyocd issue #1257. Wireless HID CMSIS-DAP bridges reorder/defer responses under load; without this, reads return cached buffers and writes silently drop. |
| `cmsis_dap.limit_packets` | `1` | Same root cause; one in-flight packet at a time. |

`target.system_reset()` is the no-halt reset path; `target.reset()` halts the
core. We use the former everywhere.

For the read-only path (`ground_station.livewatch`), `attach` +
`resume_on_disconnect=False` is also correct and is what livewatch's reader
uses. The flashtool_linux package follows the same contract. `target_override`
stays `cortex_m` in the livewatch path because the reader never issues flash
commands — but the flags above for the write path are still required for
bridge-side reads to be fresh.

## 3a. Kernel: ATK-HS-V3 HID driver binding

**Source**: Linux kernel hid driver claim order (Linux 6.8, Ubuntu Jammy/Hirsute
documented behaviour), and the CSDN writeup at
<https://blog.csdn.net/2301_79618994/article/details/160716114>.

The ATK-HS-V3 (Microchip 04d8:00df) is a composite device with two CDC-ACM
serial interfaces and one HID interface for CMSIS-DAP. The HID class claimed
by `hid_mcp2200` matches a misleading descriptor in this device, so on a
default kernel the bridge's HID endpoints get bound to `hid_mcp2200` instead
of `hid-generic`. Pyocd opens the device via `libusb`, but the underlying
HID-protocol commands get routed to a driver that doesn't speak CMSIS-DAP —
writes succeed without the bridge carrying them across SWD.

Fix once per box:

```bash
sudo cp etc-modprobe-d/blacklist-hid-mcp2200.conf /etc/modprobe.d/
sudo modprobe -r hid_mcp2200   # drop the current binding
# Replug the bridge so udev re-binds it under hid-generic.
# Verify: cat /sys/bus/hid/devices/0003:04D8:00DF.*/uevent | head -1
#         -> DRIVER=hid-generic
```

The `install hid_mcp2200 /bin/false` rule survives replugs.

---

## 4. arm-none-eabi-gcc for Cortex-M4F

**Source**: ARM, *Arm GNU Toolchain* downloads page. Tested versions:

- 14.2.Rel1 — built with and verified.
- 14.3.Rel1 / 15.2.Rel1 — also expected to work; the toolchain file is
  pinned only to the Cortex-M4F ISA (`-mcpu=cortex-m4 -mthumb
  -mfloat-abi=hard -mfpu=fpv4-sp-d16`).

**Caveats** (compared to Keil ARMCC V5.06):
- `__asm void func()` → `__attribute__((naked)) void func()` with
  `__asm volatile(...)` blocks.
- `NULL` casts on `uint32_t` DMA fields (already corrected in
  `BSP/usart3.c`, `BSP/usart4.c`, `BSP/usart5.c`).
- `--specs=nano.specs` is a linker-level option, not a compile option.

---

## 5. FreeRTOS GCC ARM_CM4F port

**Source**: FreeRTOS V9.0.0+ `FreeRTOS/Source/portable/GCC/ARM_CM4F/`. The
canonical upstream version is used. It pairs with
`FreeRTOS/portable/MemMang/heap_4.c` (selected by the `foreach` filter in
`firmware/CMakeLists.txt`).

The Keil RVDS port (`portable/RVDS/ARM_CM4F/`) is excluded by name in
`CMakeLists.txt`.

---

## 6. CI / pipeline

**Source**: GitHub Marketplace, `carlosperate/arm-none-eabi-gcc-action`.
Recommended workflow for the Linux mirror repo:

```yaml
- uses: carlosperate/arm-none-eabi-gcc-action@v1
  with:
    release: '14.2.Rel1'
```

Caches the toolchain between runs. Self-hosted runner required for any
hardware-in-the-loop step (probe must be physically attached).

---

## Cited URLs

- https://charleskorn.com/2016/04/17/a-deeper-look-at-the-stm32f4-project-template-getting-things-started/
- https://github.com/pyocd/pyOCD/blob/main/docs/options.md
- https://github.com/marketplace/actions/arm-none-eabi-gcc-gnu-arm-embedded-toolchain
- https://developer.arm.com/downloads/-/arm-gnu-toolchain-downloads

(Stored as local references; no live-link guarantee.)

---

## 7. MAVSDK offboard (agent-06)

**Source**: `mavsdk` Python package, installed from PyPI. The `System` class
wraps a MAVSDK gRPC server (bundled in the wheel); all plugin classes
(`Offboard`, `Action`) are synchronous wrappers over async gRPC stubs.

Install: `pip install mavsdk` (the wheel includes the MAVSDK server binary).

Connect: `OffboardController("serial:///dev/ttyUSB0:921600")`.

**The 20 Hz heartbeat requirement.** PX4 exits offboard if no setpoint
arrives within ~0.5 s. `OffboardController` sends a 0-velocity body
setpoint at 20 Hz (50 ms period) via `_offboard_heartbeat()` from the
moment `start_offboard()` is called until `stop_offboard()` or
`disconnect()` is called. Do not call `set_position_ned()` once and
expect the drone to hold — it will drift back to the previous mode.

**Caveat — wire-protocol.** The host-side class is `agent-06`'s scope.
The firmware side (CMD 0x21 / 0x22 MAVLink messages over USART3) is
`agent-05`'s scope. This doc entry covers only the host.

**API surface** (all async):

| Method | MAVSDK call |
|---|---|
| `connect()` | `System.connect(system_address)` |
| `arm()` | `System.action.arm()` |
| `disarm()` | `System.action.disarm()` |
| `start_offboard()` | `System.offboard.start()` |
| `stop_offboard()` | `System.offboard.stop()` |
| `set_position_ned()` | `System.offboard.set_position_ned(PositionNedYaw(...))` |
| `set_velocity_body()` | `System.offboard.set_velocity_body(VelocityBodyYawspeed(...))` |
| `takeoff()` | `arm()` + `set_position_ned(0,0,-alt,0)` |
| `land()` | `System.action.land()` |
| `goto()` | arm + start_offboard + set_position_ned |

---

## Sweep runner (agent-07)

Sweeps a parameter space on the bench without rebuilding firmware.  Schedules
samples with Sobol (low-discrepancy), Latin hypercube, or uniform random;
optimises with Nelder-Mead or a Gaussian-process surrogate (scikit-optimize,
optional).  Observable is read from telemetry (live dict lookup) or livewatch
(RAM read).

### YAML preset schema

```yaml
params:
  - name: mrac_state.pitch.What_lower_limit[0]   # DWARF-dotted name
    lo: 0.0
    hi: 0.5
observable:
  source: telemetry      # "telemetry" | "livewatch"
  name: tracking_rmse   # telemetry field name or DWARF path
  window: [0.0, 1.0]    # informational — runner reads value at settle time
schedule: sobol         # "sobol" | "random" | "latin"
optimizer: none         # "none" | "bayesian" | "nelder"
n_samples: 100
settling_time_s: 2.0
output_dir: ground_station/logs/sweeps/what_lower_limit
```

### Invocation

```bash
# Validate a preset without touching hardware
python -m ground_station.sweep_runner --validate \
  ground_station/presets/sweep_what_lower_limit.yaml

# Run a sweep (requires agent-05 MAVLink param wire transport)
python -m ground_station.sweep_runner \
  ground_station/presets/sweep_what_lower_limit.yaml
```

### Output

Each run writes a UUID-tagged subdirectory under `output_dir`:

```
output_dir/<run_id>/
  samples.csv    # one row per iteration: param columns + observable
  summary.md     # run metadata, best params, best observable value
```

The CSV is **append-safe**: if a sweep is interrupted, re-running the same
preset appends fresh rows to the existing `samples.csv`.

### Caveats

- Requires **agent-05** MAVLink param wire (SerialBridge with `set_param`) for
  the `set_param` call.  Telemetry reads work with or without agent-05.
- The runner **refuses to start** if the sweep target is not in the livewatch
  writable registry — the patch gate is enforced.
- `scikit-optimize` is optional; without it, Bayesian mode raises `RuntimeError`
  and the runner falls back to Nelder-Mead or schedule-only mode.
- The runner handles `SIGINT` / `SIGTERM` by reverting all swept params to their
  pre-sweep values before writing the CSV and exiting.

---

## MCP server (agent-04)

Exposes the bench toolchain as MCP tools so any LLM front-end (Cursor, Claude
Code, Aider) can drive the drone as a native resource. Stdio transport only for v0.

### Install

`mcp` is already in `requirements.txt`. Install it with:

```bash
pip install mcp
```

Or from the repo venv:

```bash
.venv/bin/pip install mcp
```

### Run

```bash
python -m ground_station.mcp_server   # stdio; exits on stdin EOF
# or, after installing the entry point:
mcp-drone
```

### Cursor config

`.cursor/mcp_servers.json` (checked in):

```json
{
  "mcpServers": {
    "drone-bench": {
      "command": ".venv/bin/mcp-drone"
    }
  }
}
```

### Tool list

| Tool | Description | Hardware? |
|---|---|---|
| `livewatch_read` | Read live RAM variables via SWD/UART5 | yes |
| `livewatch_verify` | Prove ELF matches flashed firmware | yes |
| `livewatch_writable` | List RAM-writable DWARF paths | no |
| `livewatch_patch` | Write a float to live RAM | yes — **safety gate** |
| `ulog_query` | Query PX4 `.ulg` files (topics/fields/series) | no |
| `param_set` | Set a MAVLink param | stub (agent-05) |
| `param_get` | Get a MAVLink param | stub (agent-05) |
| `sweep_run` | Run a parameter sweep | stub (agent-07) |
| `offboard_command` | Send MAVLink offboard command | stub (agent-06) |
| `sim_run` | Run a closed-loop simulation scenario | no |
| `sindy_fit` | SINDy sparse regression on flight logs | no |

### Caveats

- `param_set` / `sweep_run` / `offboard_command` are **stubs** until their
  respective specs ship. They return a structured `not_implemented` payload.
- `livewatch_patch` requires `i_understand=True` or the tool returns a
  `SafetyGateError` payload. This gate is enforced in the server.
- The server holds **no persistent pyocd session**. Each tool opens its
  transport context and tears it down on completion.

---

## Ulog replay (agent-01)

Turns a PX4 `.ulg` file into DataFrames indexed by timestamp (seconds). Optionally resolves ulog field names to DWARF firmware symbols.

### Install

```bash
pip install pyulog pandas    # already in requirements.txt
```

### CLI

```bash
python -m ground_station.ulog_query dump    file.ulg [--elf path] [--topic name]
python -m ground_station.ulog_query at       file.ulg --at 12.345 [--elf path]
python -m ground_station.ulog_query between   file.ulg --t0 1.0 --t1 2.5 [--topic name]
python -m ground_station.ulog_query fields   file.ulg [--elf path]
```

### DWARF resolution

DWARF resolution is best-effort — ambiguous fields fall back to raw ulog names.
Use `fields` to audit which firmware symbols your ulog actually covers:

```bash
python -m ground_station.ulog_query fields tests/fixtures/sample.ulg \
    --elf OBJ/JX_FLY.axf
```

### Library API

```python
from ground_station.ulog_reader import load_ulog, ULogReader
reader = load_ulog("flight.ulg", elf_path="OBJ/JX_FLY.axf")
df = reader.topic("vehicle_local_position")
snap = reader.at(t_seconds=12.3)
fields = reader.fields_resolved()   # ResolvedField | UnresolvedField per field
```

### Caveats

- DWARF resolution is structurally ambiguous for underscore-separated field names
  (``s_ekf_x_3`` could mean ``s_ekf.x[3]`` or ``s_ekf_x.3``); the ulog→DWARF
  converter uses the last underscore as the array index separator, and the resolver
  tries both the raw field name and the converted form against DWARF.
- `.tlog` (MAVLink UDP captures) is not yet supported.