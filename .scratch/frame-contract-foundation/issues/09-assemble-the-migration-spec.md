# Assemble and publish the migration spec

Type: task
Status: open
Blocked by: 05, 06, 07, 08, 10, 11, 12, 13, 14

## Question

The destination. Run `/to-spec` and publish with the `ready-for-agent` triage label, so
independent Cursor agents can implement the migration without reopening a single decision.

> **Rewritten 2026-07-31.** This ticket previously assembled a wave-1 spec for a field table
> generating firmware and host decoders for the fixed frames. That destination was redrawn:
> the fixed frames retire and the flexible subscription family becomes the only downlink
> telemetry, with named manifests preserving what the fixed frames carried. The original
> version is in git history; nothing below survives from it except the constraints.

Nothing here is a decision — every one is settled by the tickets above. This is the
assembly, and it is done when a fresh agent with no memory of this map can read the spec
and build the thing.

Must carry through from the resolved tickets:

- The measured goodput and loss of the new radio, and the frame-size ceiling, because every
  rate in every manifest is budgeted against them.
- Confirmation that protocol v2 works on hardware, with the run that proves it.
- The manifest form: what an entry declares, symbol names versus addresses and when they
  resolve, how the six retired frames map onto manifests, slot budgeting against
  `SUBSCRIBE_MAX_SLOTS = 4`, and where conversions live.
- The busy-DMA send policy, and whether the gcc harness's "busy-DMA skips cleanly"
  assertion still states the right thing.
- The host reader's role as sole owner of sync detection, length extraction, CRC
  verification and dispatch — and the false-sync fix, which stops being latent the moment
  subscription is the only traffic.
- The armcc gate's lane, warning policy and skip behaviour.
- The test-collection fix in **both** `pytest.ini` and `tasks.py`.

**Sequencing the spec must state explicitly, because getting it wrong is expensive:**
prove the replacement carries the load, migrate the dashboard, *then* delete the fixed
frames. Not the reverse. The fixed frames are the only working telemetry and the only
baseline to diff a migration against; deleting first leaves no instrument and no
comparison. The subscription path has never carried more than ~1600 B/s drop-free against
the ~6000 B/s that frames A+B+C represent.

Non-negotiables to state as constraints in the spec, because an agent that does not know
them will break something expensive:

- `SUBSCRIBE_ADDR_SRAM_LO/HI` stay undefined in `JX_FLY.uvprojx`. The `#ifndef` guards exist
  so the gcc harness can retarget the allowlist at host memory; defining them in the
  firmware build silently widens what a host can ask the drone to read.
- Never invoke UV4 without `<pMon>` neutralisation; go through
  `ground_station.flashtool.rebuild_and_flash`. A bare invocation claims the CMSIS-DAP probe
  and halts a powered core — it killed a live drone on 2026-07-28.
- `OBJ/JX_FLY.axf` must match the flashed image. Subscription resolves addresses from it via
  DWARF, so a mismatched .axf makes the safety gate itself read garbage. This coupling gets
  **more** load-bearing after the migration, not less.
- One process owns the CMSIS-DAP interface; the running dashboard holds COM6 exclusively.
- No flash and no target interaction without an explicit operator go-ahead in chat.
- USART3 command dispatch stays unwired. `0x21` requests are accepted on **UART5 only** —
  the new radio carries the data plane on USART3 via `SUBSCRIBE_TRANSPORT_USART3`, and the
  request path does not follow it. Do not add an inbound parser to the radio.
- `SymbolResolver` does not bounds-check array indices. Confirm array lengths from headers.
- Use the `/codebase-design` vocabulary exactly — module, interface, implementation, depth,
  deep, shallow, seam, adapter, leverage, locality. Not component, service, API, boundary,
  layer, wrapper.

Two things to check before writing, both of which may have moved:

- The suite total. 487 passing as of 2026-07-30, before the comm lane was collected.
- Whether `flight_analysis/` still sits at the repo root rather than under
  `ground_station/`. It did as of 2026-07-30, and it is why nothing imports it — but that
  belongs to the wave-3 analysis effort. Do not fix it in this spec.
