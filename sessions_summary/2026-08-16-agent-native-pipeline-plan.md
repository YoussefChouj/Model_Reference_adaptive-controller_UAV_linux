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

### Day-8+: `agent-05` — MAVLink-compatible PARAM_REQUEST_READ / PARAM_SET on UART5

**Why:** the standard primitive that every UAV research tool expects.
Unlocks MAVSDK-Python, ardupilot-mcp, and any future drone-aware
LLM tool.

**Scope:**

1. Firmware side (in `TASK/send_data.c` or a new `TASK/param.c`):
   - New CMD frame: `0xCC 0xDD | 0x21 | LEN_HI LEN_LO | name\n | value`
     where `name` is a NUL-terminated C string and `value` is `float` LE.
   - Reply frame: same `0xCC 0xDD | 0x21 | LEN | name\n | value`.
   - Backing store: a `volatile struct __param { ... } g_params[]`
     built from the same source-of-truth macros that `livewatch`
     walks. Initial population from the existing
     `params_manifest.json`.
2. Host side (`ground_station/comm/serial_bridge.py`):
   - New `set_param(name: str, value: float)` method, using the
     existing `_write_lock`.
   - New `get_param(name: str) -> float`.
   - Optional: a `pymavlink`-compatible wrapper that emits
     `PARAM_REQUEST_READ` / `PARAM_SET` messages over the same wire.
     PX4's `Tools/bench_test/bench/param_stress.py` is the
     reference.
3. Tests: offline (no hardware) using a synthetic param store;
   bench-test guarded by DISARMED.

**LOC est.:** ~400 host-side + ~200 firmware-side, ~150 tests.

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

## Open questions to resolve before `agent-05`

1. **Which param source-of-truth?** The existing
   `params_manifest.json` is hand-maintained. Should the firmware
   generate it from a single header? Today there is no central
   registry; today there are ~7 hand-edited values. Defer until
   the count grows past 20.
2. **Two-way radio (MAVLink) or just UART5 wired?** Today the bench
   is wired. Radio adds a path but not a primitive. Defer until
   flight-range testing becomes a need.
3. **What does the firmware treat as authoritative for a parameter?**
   Is `g_mrac_state.pitch.What_lower_limit` a `#define`, a global
   initialised at boot, or a runtime-mutable `volatile`? Decide
   before wiring `set_param`; otherwise writes silently no-op.

## Decision points (ask the user)

Before any of `agent-03` onward, confirm:

1. **Is `livewatch patch` desired with the `--i-understand` gate?**
   This is the only write-side change in the plan. The hardware-safety
   rule must be amended.
2. **Firmware-side param interface — UART5 vs MAVLink-only?** UART5
   is what's there; MAVLink would require a new wire format on the
   firmware. Recommend UART5 with a MAVLink-shaped frame so future
   MAVSDK wiring is a host-side change only.
3. **Build environment for firmware changes.** Linux toolchain is
   CMake + GCC. Windows is Keil + ARMCC. Any firmware-side change
   here means: edit once, both pipelines rebuild. Confirm.

## Tracking

Each spec above is a single ticket under `.agent_contracts/<TASK_ID>/spec.md`.
Use `/uav-planner` to grill the spec, `/uav-conductor` to execute,
`/uav-reviewer` to review. Standard pipeline.