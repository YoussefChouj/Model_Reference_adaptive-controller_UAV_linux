---
session_date: 2026-08-16
status: closed
purpose: After-research roadmap for the agent-native UAV pipeline.
related_research: This plan was finalised after the 2026-08-16 deep-research subagent run; see that subagent's transcript for the full source citations.
related_session: sessions_summary/2026-08-16-wireless-bridge-flash-dual-bug.md
supersedes: nothing yet.
---

# Plan — Agent-native UAV pipeline

## Goal

Make the Linux-side bench toolchain a first-class agent resource: the agent
can read state, run sweeps, inject commands, and replay past flights
without going through full-firmware rebuilds, and every one of these
primitives is exposed as an MCP tool so any LLM front-end can drive the
drone natively.

The user has stated: this is a research drone in a net-covered indoor
area. Safety constraints are dropped for this plan; the agent operates
with full bench authority. The hardware-safety rule
(`.cursor/rules/hardware-safety.mdc`) still applies to motors/arm — no
arming, no motor spin, no probe-tooling bypass. Everything else is in
scope.

## Constraints (real, not invented)

* **Read path** is already strong. `livewatch` resolves any DWARF
  symbol over SWD/UART5 and runs freshness probes. Most "missing"
  capabilities are write-side.
* **Firmware side** has no MAVLink param interface. The `CMD` frame
  protocol on UART5 (`0xCC 0xDD`) does have writes for SysID injection,
  OF calibration, and force-recal — but no general param_set. Adding
  one is a small firmware-side change.
* **Build side** is on Windows with Keil uVision + ARMCC V5.06.
  Linux-side is CMake + arm-none-eabi-gcc. Anything that requires
  `firmware/build/...` is the Linux pipeline; anything in `OBJ/...`
  is the Windows pipeline. The same `livewatch` reads either.
* **Wireless bridge** is the only probe available. Direct `pyocd
  flash --target stm32f407zgtx` is the working path; `tasks.py flash`
  has the documented IPSR=3 caveat. RAM-write primitives will run on
  the same bridge and inherit the same caveat.

## What is already in place

| Capability | Where | Status |
|---|---|---|
| DWARF symbol resolution | `ground_station/livewatch/symbols.py` | present |
| Read RAM by name | `ground_station/livewatch/reader.py` | present |
| ELF-vs-flash integrity check | `ground_station/livewatch/verify.py` | present (5 chunks) |
| Wireless-bridge preflight | ADR-0015, `pyocd.yaml`, `scripts/setup_linux_toolchain.sh` | present (committed `7c18346`, `1bd4d21`, `54d7edc`) |
| Telemetry frame A/B/C/0x03–0x05 | `ground_station/comm/serial_bridge.py` | present, host-side writes for SysID/OF/force-recal |
| Bench command host-side write path | `ground_station/comm/serial_bridge.py:_write_lock` | present, but no general param_set |
| Offline flight CSV logs | `sim/sindy/flight_loader.py` | present, no ulog reader |
| Sim `Plant` ABC + MuJoCo + Gazebo retired | `sim/plant.py`, `sim/mujoco_plant.py` | present |
| SINDy / flight_loader | `sim/sindy/` | present, works on CSV only |

## What is missing — and the cost of each gap

| Gap | What it costs the agent |
|---|---|
| No general live parameter SET | Every parameter change → C-edit → rebuild → flash. A 10-step sweep is hours, not minutes. |
| No ulog/tlog reader | Past flights are unreadable to the agent except via ad-hoc CSV export. The DWARF-↔-log join is impossible. |
| No watchpoints | Cannot say "stop at the line that corrupts `s_ekf.x`"; profiling is by polling. |
| No MCP server | Agent tools are ad-hoc shell commands. Every LLM front-end has to learn the bespoke CLI. |
| No on-target scripting | Even small logic changes ("if `e_freeze > 8` then log") require a rebuild. |
| No flight replay from DWARF-resolved logs | Post-flight analysis is manual. |

## Roadmap — what to ship, in order

### Hour-1 / Day-1: `agent-01` — `.ulg` flight replay tied to DWARF symbols

**Why first:** zero firmware risk, zero probe needed, immediately useful,
half-built already. Every downstream spec needs an observable metric;
flight logs are the canonical source.

**Scope:**

1. Add `pyulog` to `requirements.txt` (it's pre-installed in `sim/`'s
   venv already — verify, then `pip install pyulog`).
2. New file `ground_station/ulog_reader.py`:
   - Use `from pyulog import ULog` to load a `.ulg` file.
   - For each topic, walk `topic.data` keys. For each key that is a
     DWARF symbol path (e.g. `s_ekf.x[3]`), resolve via existing
     `SymbolResolver("firmware/build/JX_FLY.elf")` to confirm the
     address is in `.bss` / `.data` (RAM).
   - Return a dict of `pandas.DataFrame`s keyed by topic, with DWARF
     names as columns.
3. New CLI: `python -m ground_station.ulog_query <file.ulg>
   --elf firmware/build/JX_FLY.elf --at 12.345 --what s_ekf.x[3]
   mrac_state.pitch.What`.
4. Tests: `tests/test_ulog_reader.py` — synthetic ulog + the existing
   `firmware/build/JX_FLY.elf`, assert column mapping.
5. Docs: add a short "ulog replay" section to `docs/linux-pipeline-references.md`.

**LOC est.:** ~150 host-side, ~80 tests.

**Caveat:** until the project actually records `.ulg` from real flights,
the reader's data source will be synthetic. That is fine — the agent
gets the API and tests first, real data follows once a flight recorder
is added.

### Day-2 / Day-3: `agent-02` — DWARF-walkable writable-address registry

**Why second:** rebuild-proof enumeration of every RAM-resident tunable.
Pairs with `agent-01` to make the agent self-aware of what it can ask
the firmware to do.

**Scope:**

1. Extend `ground_station/livewatch/symbols.py:SymbolResolver` with
   `writable_members(base_name: str) -> list[WritableField]`.
2. A `WritableField` carries `(address, c_type, name)` — only members
   whose DWARF `DW_AT_location` describes a RAM address (filter by
   `DW_OP_addr` is in `.bss` / `.data`, not `.text`, not a register).
3. Cache to `firmware/build/writable_registry.json` on each rebuild
   (`ground_station/flashtool_linux/linux_build.py`).
4. CLI: `python -m ground_station.livewatch writable mrac_state`.

**LOC est.:** ~100 host-side, ~50 tests.

### Day-4 / Day-5: `agent-03` — `livewatch patch` (gated RAM write)

**Why:** the missing primitive. Without it, no parameter sweep is
possible. With it, every parameter in `writable_registry.json`
becomes addressable by name.

**Scope:**

1. Add `pyocd` write primitives to
   `ground_station/livewatch/transport.py`:
   - `target.write_memory_block32(addr, [values])` over SWD.
   - Read-back verify after every write (mandatory).
   - Halt-and-resume dance around each write so the firmware's own
     task can't observe a torn 32-bit write.
2. New `livewatch patch` CLI:
   ```
   python -m ground_station.livewatch patch \
       mrac_state.pitch.What_lower_limit 0.5
   ```
   With `--dry-run`, `--verify-only`, and `--gates`
   ("don't proceed unless ARM_Status == DISARMED").
3. Tests: offline test against a synthetic SymbolResolver; bench
   test guarded by an explicit "this is a write" print banner that
   the operator must acknowledge.
4. **NOT** in `livewatch`'s default behaviour. Required `--i-understand`
   flag.

**LOC est.:** ~120 host-side, ~80 tests.

**Safety carve-out:** the read-only contract in
`.cursor/rules/hardware-safety.mdc` is correct. This spec carves out a
specific, named-symbol RAM write primitive, gated on `--i-understand`
+ DISARMED. Document the carve-out in the rule.

### Day-6 / Day-7: `agent-04` — MCP server v0

**Why:** standardises the agent's tool surface. Cursor / Claude Code /
Aider / any MCP-aware LLM can call these as native tools. The
arxiv paper (Universal LLM-Drone C2 via MCP, 2601.15486v2) and two
GitHub implementations (`rmeadomavic/ardupilot-mcp`,
`Project-GrADyS/uav_mcp`) validate the pattern.

**Scope:**

1. Add `mcp` Python SDK to `requirements.txt`.
2. New file `ground_station/mcp_server.py`:
   - Tools: `livewatch_read`, `livewatch_verify`, `livewatch_patch`,
     `livewatch_writable`, `ulog_query`, `sweep_run`, `sindy_fit`,
     `sim_run`.
   - StdIO transport (default) + optional HTTP transport.
3. `pyproject.toml` entry point: `mcp-drone` → `ground_station.mcp_server:main`.
4. Cursor / Claude Code config block (`mcp_servers` section) checked
   into the repo under `.cursor/mcp_servers.json`.

**LOC est.:** ~300 host-side, ~50 tests.

### Day-8+: `agent-05` — MAVLink-compatible PARAM_REQUEST_READ / PARAM_SET on USART3

**Why:** the standard primitive that every UAV research tool expects.
Unlocks MAVSDK-Python, ardupilot-mcp, and any future drone-aware
LLM tool. The wire is **USART3** (the long-range radio), not UART5.
Per the user's clarification and the wiki's
`uart-peripheral-map.md` USART3 section: UART5 is the wireless
dongle's VCP and must stay telemetry-only.

**Prerequisite:** the two firmware defects in `usart3_send()`
(`TASK/send_data.c:318-358`) — DMA reads a dead stack frame, and
busy-wait throttles `Send_Task` to ~60 Hz. These are documented in
the wiki and need their own small spec (`agent-04b`) before
USART3 can carry bidirectional traffic. Otherwise the agent-control
path is fundamentally broken.

**Scope:**

1. Firmware side (in `TASK/send_data.c` or new `TASK/param.c`):
   - New CMD frame on USART3, MAVLink-shaped:
     `0xFE 0x21 | LEN | SEQ | SYSID | COMPID | msgid (PARAM_SET) | name\n | value`.
   - Reply on USART3, same shape, msgid = PARAM_VALUE.
   - Backing store: a `volatile struct __param { ... } g_params[]`
     built from the same source-of-truth macros that `livewatch`
     walks. Initial population from the existing
     `params_manifest.json`.
   - The USART3 RX handler is currently a stub
     (`TASK/stm32f4xx_it.c:115-123` discards the byte). Wire it
     to a `param_set` dispatcher.
2. Host side (`ground_station/comm/serial_bridge.py`):
   - New `set_param(name: str, value: float)` method, using the
     existing `_write_lock` and a new `USART3_PATH` constant.
   - New `get_param(name: str) -> float`.
   - `pymavlink` wrapper that emits `PARAM_REQUEST_READ` /
     `PARAM_SET` over the wire. PX4's
     `Tools/bench_test/bench/param_stress.py` is the reference.
3. Tests: offline (no hardware) using a synthetic param store;
   bench-test guarded by DISARMED.

**LOC est.:** ~400 host-side + ~300 firmware-side (incl. the USART3
fix), ~150 tests.

### Day-9: `agent-06` — Sobol / Bayesian sweep runner

**Why:** turns the param-set primitive into autonomous tuning.

**Scope:**

1. New `ground_station/sweep_runner.py`:
   - `scipy.stats.qmc.Sobol` for the schedule (already in venv via
     scipy 1.18).
   - `scipy.optimize.minimize(method='gp_minimize')` for Bayesian
     updates (or simple Nelder-Mead if GP is overkill).
   - YAML manifest: parameter ranges + observable metric (telemetry
     field name or `livewatch`-resolvable symbol).
   - Logs every iteration to `ground_station/logs/sweeps/<id>/`.
2. CLI: `python -m ground_station.sweep_run
   ground_station/presets/sweep_what_lower_limit.yaml`.

**LOC est.:** ~250 host-side, ~80 tests.

### Day-10+: `agent-07` — on-target Duktape scripting (optional)

**Why:** ultimate unlock — agent injects arbitrary logic. ~160 KB ARM,
~32 KB RAM footprint. Embeddable in the existing build.

**Scope:** TBD, only after the bench-side sweep runner proves useful
in a real tuning loop. The Lua-pattern C bindings (`param:get`,
`param:set`) already exist in Ardupilot's `libraries/SCRIPTING/` —
port that pattern.

**LOC est.:** ~1500 host + firmware, defer.

### Day-30+: `agent-08` — HITL via MuJoCo + real FC

The existing `Plant` ABC + `MujocoPlant` covers sim. Adding HITL
means the FC runs against the MuJoCo plant instead of real
sensors. Defer — `agent-01` to `agent-06` ship first.

## Day-1 plan (executable now)

```bash
# Pre-flight (ADR-0015):
.venv/bin/python tasks.py doctor
.venv/bin/python -m pyocd list --targets | grep stm32f407   # DFP installed
ls /sys/bus/hid/devices/0003:04D8:00DF.*/uevent | head -1    # DRIVER=hid-generic

# Step 1 — install pyulog
.venv/bin/python -m pip install pyulog pandas pyarrow

# Step 2 — write ground_station/ulog_reader.py
# Use existing SymbolResolver from ground_station/livewatch/symbols.py.
# Topic → DWARF column mapping. Skip absent DWARF matches gracefully.
# Time-index query: --at <seconds>, --between <a> <b>.

# Step 3 — test
.venv/bin/python -m pytest ground_station/tests/test_ulog_reader.py -q

# Step 4 — commit
git add requirements.txt ground_station/ulog_reader.py ground_station/tests/test_ulog_reader.py
git commit -m "feat(ulog): reader with DWARF-aware column mapping for flight replay"
```

That's it. One hour of code, one afternoon of tests, the agent gains
a flight-replay tool that no other repo has wired together.

## What I am NOT proposing (and why)

* **probe-rs (Rust) integration.** Pyocd + `livewatch` already cover
  the agent's needs. probe-rs would be a re-write for marginal
  gain. Revisit only if pyocd watchpoints fail.
* **RTT / Segger channel.** Requires a J-Link probe we don't have.
  Deferred until hardware changes.
* **Full Gazebo SITL.** MuJoCo + `Plant` ABC already gives HITL-class
  capabilities offline. Adding Gazebo is duplicate work.
* **HITL firmware build (`HIL_ACTUATOR_CONTROLS` path).** Firmware-side
  HITL build is its own project. Defer.
* **Betaflight MSP-style sliders.** Our protocol is a single binary
  protocol; bolting MSP on is unjustified complexity.
* **Re-pointing Frame A/B telemetry to USART3.** USART3 tops out at
  ~960 B/s at 9600 baud — Frame A/B is 8.6 kB/s. Won't fit. Stay
  with UART5 for telemetry. USART3 is for low-rate agent commands
  only.

## Open questions to resolve before `agent-05`

1. **Which param source-of-truth?** The existing
   `params_manifest.json` is hand-maintained. Should the firmware
   generate it from a single header? Today there is no central
   registry; today there are ~7 hand-edited values. Defer until
   the count grows past 20.
2. **Radio range vs UART5 wired?** Decided: agent-control on
   USART3 (long-range). UART5 stays telemetry-only.
3. **What does the firmware treat as authoritative for a parameter?**
   Is `g_mrac_state.pitch.What_lower_limit` a `#define`, a global
   initialised at boot, or a runtime-mutable `volatile`? Decide
   before wiring `set_param`; otherwise writes silently no-op.
4. **Prerequisite `agent-04b`: fix `usart3_send()` first.**
   The wiki documents two defects in `usart3_send()`
   (`TASK/send_data.c:318-358`):
   - DMA reads a dead stack frame (`str_USART[16]` is local but
     `extern`'d in `send_data.h:19`).
   - Busy-wait throttles `Send_Task` to ~60 Hz.
   Without fixing these, USART3 cannot carry agent traffic and
   `Send_Task` is also capped. ~30 LOC fix in firmware.

## Decisions

**User-confirmed 2026-08-16:**

1. **`livewatch patch` with the `--i-understand` gate is approved.**
   The read-only contract in `hardware-safety.mdc` is amended to
   carve out a named-symbol RAM write primitive, gated on
   `--i-understand` + ARM_DISARMED. The carve-out is a
   `hardware-safety.mdc` revision, separate spec.
2. **Build environment for firmware changes: Linux first.**
   Linux pipeline (CMake + arm-none-eabi-gcc) is the primary
   iteration loop. Windows Keil/ARMCC mirror is downstream.
3. **Param/agent-control wire: USART3, not UART5.**
   The user's clarification: UART5 is wired through the wireless
   CMSIS-DAP dongle (limited rate/range) and must remain telemetry.
   USART3 goes to the long-range radio module — that is the
   agent-control channel. The firmware-side defects documented in
   `wiki/concepts/uart-peripheral-map.md` (`usart3_send()` reads a
   dead stack frame + busy-wait caps `Send_Task` at 60 Hz) must be
   fixed first — they are not part of agent-05 itself, but they
   block any USART3 work.

**Still open:** the frame layout on USART3. Recommend MAVLink-shaped
over the existing `0xCC 0xDD` style, so the host side can re-use
`pymavlink` directly. Document the choice in `agent-05` when the
spec is written.

## Stale-wiki finding (2026-08-16, post-research)

`agent-04b` ("fix `usart3_send()` defects") was conceived from
`wiki/concepts/uart-peripheral-map.md`. The wiki is **stale** in two
specific ways:

1. The wiki says `str_USART[16]` is a *local* whose address is
   handed to DMA1_Stream3. **The current code
   (`TASK/send_data.c:489`) makes it `static`.** The dead-stack
   defect is fixed.
2. The wiki says a busy-wait throttles `Send_Task` to 60 Hz.
   **The current code uses a continuous TX ring
   (`BSP/usart3.c:202-326`, `Usart3_Stream_TxSend`)** with no busy-wait
   on the producer side. The producer copies bytes into the ring,
   arms the DMA, returns. The DMA IRQ drains back to back.

The whole TX side was already redesigned for the MicoAir WiFi Link
swap (2026-08-09, comments in `TASK/send_data.c:484-602` and
`BSP/usart3.c:14-25, 176-201`).

Also: USART3 is **already a bidirectional 0xCC 0xDD command
ingress** (`BSP/usart3.c:12-25`, `TASK/stm32f4xx_it.c:115-141`,
wired 2026-08-09). The dispatch path is `Handle_USART3_GroundStation_Command`
mirroring the UART5 path.

**Conclusion:** `agent-04b` is **already done** — there is no
firmware work. The wiki needs a `## Stale` annotation or a
rewrite. The actual work that remains for agent-05 is **adding
new CMD codes (0x21 PARAM_SET, 0x22 PARAM_GET) to the existing
parser**, which is a small spec — not the "fix USART3" spec the
plan described.

The implementer of agent-05 should verify this finding against the
actual source and report it in the journal — do not blindly assume
the wiki is right.

## Tracking

Each spec above is a single ticket under `.agent_contracts/<TASK_ID>/spec.md`.
Use `/uav-planner` to grill the spec, `/uav-conductor` to execute,
`/uav-reviewer` to review. Standard pipeline.