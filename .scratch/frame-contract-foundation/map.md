# Map: Frame contract foundation (deepening wave 1)

Label: wayfinder:map
Created: 2026-07-30

## Destination

A published, `ready-for-agent` **wave-1 spec** that independent Cursor agents can
implement with no decisions left open, covering: one **Frame envelope** module owning
sync words / length / CRC selection for the downlink; one **field table** as the single
source of truth for the **fixed frames**, generating both the firmware header and the
host module; the test-collection gap that let four wire-layout sites drift unnoticed;
and an **armcc conformance gate** so the real Keil dialect is checked on every change.

Wave 1 is deliberately behaviour-preserving on the wire. Nothing here changes a byte
that the drone currently transmits.

## Notes

- **Domain**: STM32F4 quadrotor research platform. Two telemetry families, and the
  distinction is load-bearing for every ticket on this map:
  - **Fixed frames** — Frame A (`0x01`), B (`0x02`), C (`0x06`), ID (`0x03`), bench, OF.
    Built by open-coded buffer writes in `Send_Groundstation_Telemetry_UART4()`, decoded
    by six `_unpack_frame_*` methods on the host. Layout exists only as source in two
    places, so drift is silent. **This is what wave 1 fixes.**
  - **Flexible telemetry** — CMD `0x20` poll and CMD `0x21` streaming subscription.
    Already deep: the `0x08` schema frame carries the layout *on the wire*, so the host
    cannot structurally drift, and `decode_schema` refuses a schema echoing a range that
    was not requested. Contract is the `API/subscribe.h` header comment. **Read it before
    touching anything here, and do not redesign it.**
- **Both families already share one downlink envelope**: `0xAA 0xBB | TYPE | LEN_HI |
  LEN_LO | payload | CRC-trailer`, open-coded 6× in `send_data.c` and 4× in
  `subscribe.c`. Uplink has two prefixes: `0xCC 0xDD` (fixed 9-byte command) and
  `0xCC 0xDE` (extended, length-prefixed).
- **Seams, confirmed with the user 2026-07-30** — two seams and one gate, no new
  firmware seam invented:
  1. **Firmware C on host, `gcc -m32`** — extends the existing pattern in `API/tests/`
     driven from `ground_station/livewatch/tests/test_subscribe_c.py`. Compile the
     envelope module standalone, build each envelope, assert the host reader parses it.
     One seam, both sides.
  2. **Host Python at the existing interface** — the six `_unpack_frame_*` methods and
     the two VOFA channel-name builders already *are* the interface. Assert every field
     list equals the table; assert regeneration produces no diff. No new seam.
  3. **armcc conformance** — a gate, not a seam. Exit code only.
  Deferred to wave 2: round-tripping the whole emitter. `subscribe.c` needed 5 stubs;
  `send_data.c` pulls ~15 headers and ~90 globals, so the stub surface costs more than it
  returns until the emitter is split.
- **Table form, confirmed with the user 2026-07-30**: a machine-readable data file is
  the contract; it generates the firmware header **and** the host module; both generated
  files are committed; a test asserts regeneration produces no diff. Matches how
  `ground_station/livewatch/log_frames.md` and `livewatch/manifests.yaml` already work,
  and Keil lists files explicitly so generated output must be checked in regardless.
- **Research-platform framing (user, 2026-07-30)**: indoor, enclosed, protected. A crash
  costs nothing; debugging friction and silently-wrong data cost everything. Vehicle
  safety constraints (props-off, motor twitch, blast radius) do **not** gate this work.
  Three toolchain constraints DO still hold, because they protect access and data
  integrity rather than the airframe:
  - `OBJ/JX_FLY.axf` must match the flashed image — livewatch and the flash gate resolve
    symbol addresses from it.
  - One process owns the CMSIS-DAP probe; never invoke UV4 without neutralising `<pMon>`.
    Always go through `ground_station.flashtool.rebuild_and_flash`.
  - `SUBSCRIBE_ADDR_SRAM_LO/HI` must never be defined in `JX_FLY.uvprojx`.
- **Knowledge stack first** every session: `ccc search`, then `graphify-out/GRAPH_REPORT.md`,
  then `wiki/index.md`, then `docs/decisions.md`. The PreToolUse hook blocks Grep/Glob
  until `python .agent_scripts/knowledge_gate.py --unlock`, and it requires explicit
  `--touch ccc|graphify|wiki` calls — reading the files does not register.
- **Skills to consult**: `/codebase-design` for the vocabulary (module, interface, depth,
  seam, adapter, leverage, locality — use these exactly), `/grilling` and
  `/domain-modeling` per ticket, `/to-spec` for the final assembly ticket.
- **Executors**: independent Cursor agents implement the spec. Every decision must be
  written down where an agent with no memory of this session will find it.
- Relevant ADRs, not to be re-litigated: the 2026-04-12 XOR-CRC decision (wave 1 keeps
  XOR on the fixed frames; the CRC16 already shipped on the flexible data plane), and
  the 2026-04-12 multi-rate task partitioning.

## Decisions so far

<!-- one line per closed ticket: gist + link -->

_None yet — map charted 2026-07-30._

## Not yet specified

- **The Frame envelope module's CRC-policy interface.** Three policies coexist today:
  a per-frame self CRC used by the A+C burst, a whole-buffer CRC, and CRC16-CCITT on the
  flexible data plane. Whether the envelope exposes one parameter, a policy enum, or two
  entry points can't be phrased sharply until [Does the flexible-telemetry path adopt the
  Frame envelope in wave 1?](issues/04-subscribe-adopts-envelope.md) settles which
  families share it.
- **Whether the field table also generates the human-readable protocol documentation.**
  `docs/interfaces.md` and `wiki/concepts/ground-station-binary-protocol.md` are two of
  the four already-drifted sites. Generating them would close that class entirely, but
  the shape depends on what the table's scope turns out to be.
- **Whether LEN becomes computed everywhere.** Five length literals exist in the emitter
  and only Frame C back-fills LEN from bytes actually written. Sharp once the table's
  handling of runtime-variable groups is decided.
- **The setpoint write-site audit as a wave-1 byproduct.** The table work will read most
  of `send_data.c` anyway; an audit doc naming every writer of `Ctrler.*.Des` is nearly
  free at that point and is the prerequisite for the wave-3 setpoint-ownership work.
  Not sharp until the spec's file scope is fixed.
- **Disposition of dead code in the emitter** — `ANO_Report_UserData1` (119 lines, zero
  callers, would DMA into UART5 mid-telemetry), `send_to_linux` (early-returns, port
  unclocked), and `send_data.h`'s stale `extern UCHAR8 str_USART[16]` which no longer
  exists. Probably wave 2, alongside the emitter split.

## Out of scope

- **Waves 2 and 3 in their entirety** — each is a fresh effort whose shape depends on
  what wave 1 produces:
  - emitter split of `Send_Groundstation_Telemetry_UART4` (655 lines, 5 fused concerns)
  - command decode/apply split with a per-command in-flight policy column
  - one UART port module, and moving fixed telemetry onto USART3 once the BLE radio lands
  - dashboard derivation extraction, then the GUI reorganisation
  - resolving the two analysis generations onto `flight_analysis/`
  - `rebuild_and_flash` dedup onto its tested modules
  - setpoint ownership for `Ctrler.*.Des`
- **Extending the SIL gate to `mrac.c` with a gcc-parity lane.** Its own destination —
  executing the firmware's adaptive law against `sim/`'s Python rather than asserting
  parity. The armcc gate chartered here is a shared prerequisite, not the same effort.
- **Raising the UART5 baud rate.** 42 sites across 18 files including the dashboard.
- **Any change to the on-wire bytes.** Wave 1 is behaviour-preserving by construction;
  a wire change is what makes the no-diff and round-trip tests meaningful.
