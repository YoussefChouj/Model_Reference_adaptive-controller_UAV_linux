# Map: Frame contract foundation

Label: wayfinder:map
Created: 2026-07-30
**Destination redrawn: 2026-07-31**

## Destination

A published, `ready-for-agent` **migration spec** that independent Cursor agents can
implement with no decisions left open, taking the downlink from two telemetry families to
one: the **flexible subscription family** becomes the only telemetry path, and the content
of today's fixed frames is preserved as **named manifests** the subscription selects — so a
known-good set of variables at known rates is recoverable by name rather than reconstructed
from memory.

> **What changed and why.** The original destination was a behaviour-preserving *wave 1*: a
> Frame envelope module, a field table generating firmware and host decoders for the fixed
> frames, and an armcc gate — changing no byte on the wire. Grilling
> [How does the field table express runtime-variable repeated groups?](issues/01-runtime-variable-groups-in-the-field-table.md)
> surfaced the operator's actual purpose for the link: it must absorb additions and
> subtractions as the controller evolves, up to neural networks in the adaptive layer. The
> fixed frames measurably cannot carry that — the repeat count is a single byte capped at
> 255, and the link already runs at 101% of capacity with Frame B alone taking 43%. The
> flexible family already solves it structurally by putting the layout **on the wire**, so
> the host cannot drift. Generating code for frames that are being deleted was the most
> expensive item on the old map and the least likely to survive. Confirmed with the operator
> 2026-07-31, together with the arrival of a replacement radio at 8x the current baud, which
> is what makes the bandwidth arithmetic work.

Sequencing is part of the destination: **prove, migrate, then delete.** The fixed frames
stay until the replacement is measured carrying the load and the dashboard is moved onto it.

## Notes

- **Domain**: STM32F4 quadrotor research platform. Two telemetry families today; one at the
  destination.
  - **Fixed frames** — Frame A (`0x01`), B (`0x02`), C (`0x06`), ID (`0x03`), bench, OF.
    Open-coded buffer writes in `Send_Groundstation_Telemetry_UART4()`, decoded by six
    `_unpack_frame_*` methods on the host. Layout exists only as source in two places, so
    drift is silent. **These retire.**
  - **Flexible telemetry** — CMD `0x20` poll and CMD `0x21` streaming subscription. The
    `0x08` schema frame carries the layout on the wire, so the host cannot structurally
    drift, and `decode_schema` refuses a schema echoing a range that was not requested.
    Contract is the `API/subscribe.h` header comment. **Read it before touching anything
    here, and do not redesign it. This becomes the only family.**
- **The downlink envelope is 6 bytes, not 5** — corrected 2026-07-31, the original Notes
  were wrong:
  `0xAA 0xBB | TYPE | LEN_HI | LEN_LO | BYTE5 | payload | CRC`.
  **Byte 5 is polymorphic** and CRC-covered: `MAX_NUM_BASIS` on the fixed frames, tuple or
  range count on `0x07`/`0x7F`/`0x08`, and **`seq` on the `0x09+slot` data frames**. Any
  envelope work must treat it as opaque — an envelope that reads it as a count cannot carry
  a sequence number. Uplink has two prefixes: `0xCC 0xDD` (fixed 9-byte command) and
  `0xCC 0xDE` (extended, length-prefixed).
- **The architecture already anticipates the migration.** `SUBSCRIBE_TRANSPORT_USART3 = 1`
  exists (`API/subscribe.h:200`), and a USART3 stream already suppresses `usart3_send()` and
  owns the link. The dashboard reads a snapshot dict of **named keys** through
  `_sync_telemetry_from_bridge_if_local` — three touch points, not per-frame internals — so
  a manifest populating the same key names leaves it largely unchanged.
- **Manifest precedent, already shipped**: `ground_station/livewatch/log_frames.md` is a
  Markdown table that is the source of truth for stream frames and **needs no rebuild to
  change**. `livewatch/manifests.yaml` and `params_manifest.json` are the other two
  data-as-contract artefacts.
- **Measured facts the rate budget rests on**:
  - UART5 is ~101% saturated: 11677 B/s against an 11520 B/s cap.
  - Frames after the 2026-07-29 DMA race fix: `0x01` ~65 Hz, `0x06` ~65 Hz, `0x02` 16.3 Hz.
    Frame B is 305 B x 16.3 Hz ~= 4971 B/s — 43% of the whole downlink on its own.
  - Subscription's real drop-free ceiling is **~1600 B/s**, not the 2304 B/s the firmware
    permits; 2055 B/s dropped 14% on every slot. A+B+C is ~6000 B/s, so the migration asks
    it to carry ~4x what it has ever done cleanly.
  - The previous radio at 115200 measured **5413 B/s at 0.14% loss** — 47% of line rate,
    with frames degrading above ~104 B. Apply the same discount to the new module's 921600
    and 8x becomes ~4x. Unmeasured until ticket 10.
  - `MAX_NUM_BASIS` is compile-time (`API/mrac.h:80-96`) and takes **four** values — 4, 6, 8
    or 10 — selected by `USE_STRUCTURED_UNCERTAINTY` x `INCLUDE_CONTROL_IN_REGRESSOR`.
    Currently 6. Never copy the number; resolve it.
- **Research-platform framing (user, 2026-07-30)**: indoor, enclosed, protected. A crash
  costs nothing; debugging friction and silently-wrong data cost everything. Vehicle safety
  constraints do **not** gate this work. Three toolchain constraints DO hold, because they
  protect access and data integrity rather than the airframe — and the first gets **more**
  load-bearing after the migration, since subscription resolves addresses from the .axf:
  - `OBJ/JX_FLY.axf` must match the flashed image.
  - One process owns the CMSIS-DAP probe; never invoke UV4 without neutralising `<pMon>`.
    Always go through `ground_station.flashtool.rebuild_and_flash`.
  - `SUBSCRIBE_ADDR_SRAM_LO/HI` must never be defined in `JX_FLY.uvprojx`.
- **USART3 command dispatch stays unwired — deliberate.** `0x21` requests are accepted on
  UART5 only. The new radio carries the data plane on USART3; the request path does not
  follow it. Do not add an inbound parser.
- **Knowledge stack first** every session: `ccc search`, then `graphify-out/GRAPH_REPORT.md`,
  then `wiki/index.md`, then `docs/decisions.md`. The PreToolUse hook blocks Grep/Glob until
  `python .agent_scripts/knowledge_gate.py --unlock`, and it requires explicit
  `--touch ccc|graphify|wiki` calls — reading the files does not register.
- **Skills to consult**: `/codebase-design` for the vocabulary (module, interface, depth,
  seam, adapter, leverage, locality — use these exactly), `/grilling` and
  `/domain-modeling` per ticket, `/to-spec` for the final assembly ticket.
- **Executors**: independent Cursor agents implement the spec. Every decision must be
  written down where an agent with no memory of this session will find it.
- Relevant ADRs, not to be re-litigated: the 2026-04-12 XOR-CRC decision and the 2026-04-12
  multi-rate task partitioning.

## Decisions so far

<!-- one line per closed ticket: gist + link -->

- [How does the field table express runtime-variable repeated groups?](issues/01-runtime-variable-groups-in-the-field-table.md)
  — **ruled out of scope; it redrew the destination.** No field table will be built. Durable
  findings recorded on the ticket: the envelope is 6 bytes with a polymorphic byte 5;
  `MAX_NUM_BASIS` is compile-time with four possible values; Frame B is 4 axes (code right,
  comment stale); and the fixed frames cannot carry a neural adaptive layer at any rate
  worth having.

## Not yet specified

- **Rate budgeting across the four slots.** `SUBSCRIBE_MAX_SLOTS` is 4 and today's frames
  want ~65 / ~65 / 16.3 Hz. Whether that fits, and what gets demoted if it does not, is
  arithmetic that cannot be done until [Characterise the new radio's real
  goodput](issues/10-characterise-new-radio-goodput.md) returns a number.
- **The dashboard's migration onto manifest-sourced telemetry.** Coupling looks shallow —
  a snapshot dict of named keys — but the shape depends on what a manifest entry declares.
  Sharp once [What does a named manifest declare?](issues/13-manifest-form.md) settles.
- **Deleting the fixed-frame emitter and the six host decoders.** The destination itself.
  Blocked on everything; not specifiable until the replacement is proven carrying the load.
- **Deduplicating the four open-coded envelope sites in `subscribe.c`** (`:240, 296, 566,
  613`). A genuine but small deepening, and the only envelope work left once the six
  fixed-frame sites are gone.
- **Whether a protocol version byte survives at all.** A schema-on-the-wire family has no
  host-side layout constant to keep in sync, so `GS_PROTO_VERSION`'s job may simply vanish
  — or may survive as a compatibility marker. Not sharp until the manifest form is fixed.
- **Whether manifests generate the human-readable protocol documentation.**
  `docs/interfaces.md` and `wiki/concepts/ground-station-binary-protocol.md` are both
  already drifted, and a manifest is the natural source.
- **Disposition of dead code in the emitter** — `ANO_Report_UserData1` (119 lines, zero
  callers, would DMA into UART5 mid-telemetry), `send_to_linux` (early-returns, port
  unclocked), and `send_data.h`'s stale `extern UCHAR8 str_USART[16]` which no longer
  exists. Rides along with the emitter's deletion.
- **The setpoint write-site audit.** An audit doc naming every writer of `Ctrler.*.Des` is
  the prerequisite for the wave-3 setpoint-ownership work. Not sharp until this map's file
  scope is fixed.

## Out of scope

- **A field table generating firmware and host decoders for the fixed frames** — closed
  with the destination redraw. See [ticket 01](issues/01-runtime-variable-groups-in-the-field-table.md),
  [02](issues/02-table-scope-and-proto-version-ownership.md),
  [03](issues/03-generated-code-into-the-keil-build.md). The frames are being deleted, so
  generating code for them is work with no future. Byte-layout knowledge that survives is
  recorded on ticket 01.
- **A Frame envelope module shared between the two families** —
  [ticket 04](issues/04-subscribe-adopts-envelope.md). There is no second family at the
  destination, so there is nothing to share.
- **Raising the UART5 baud rate.** 42 sites across 18 files including the dashboard. The new
  radio on USART3 makes it moot.
- **Waves 2 and 3 in their entirety** — each a fresh effort:
  - emitter split of `Send_Groundstation_Telemetry_UART4` (655 lines, 5 fused concerns) —
    now subsumed by deleting it outright
  - command decode/apply split with a per-command in-flight policy column
  - one UART port module
  - dashboard derivation extraction, then the GUI reorganisation
  - resolving the two analysis generations onto `flight_analysis/`
  - `rebuild_and_flash` dedup onto its tested modules
  - setpoint ownership for `Ctrler.*.Des`
- **Extending the SIL gate to `mrac.c` with a gcc-parity lane.** Its own destination. The
  armcc gate chartered here is a shared prerequisite, not the same effort.
