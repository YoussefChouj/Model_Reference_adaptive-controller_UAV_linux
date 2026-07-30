# Assemble and publish the wave-1 spec

Type: task
Status: open
Blocked by: 01, 02, 03, 04, 05, 06, 07

## Question

The destination. Run `/to-spec` and publish the spec with the `ready-for-agent` triage
label, so independent Cursor agents can implement it without reopening a single decision.

Nothing here is a decision — every one is settled by the tickets above. This ticket is the
assembly, and it is done when a fresh agent with no memory of this map can read the spec
and build the thing.

Must carry through from the resolved tickets:

- The two confirmed seams and the one gate, verbatim from the map's Notes. Firmware C on
  host via `gcc -m32` extending the `API/tests/` pattern; host Python at the existing
  `_unpack_frame_*` and VOFA channel-name interface; armcc conformance as an exit-code
  gate. Full emitter round-trip is wave 2, and the spec should say why.
- The table's expressiveness for runtime-variable groups, and the generated output on both
  sides.
- Frame coverage and whether the table owns `GS_PROTO_VERSION`.
- How generated code reaches ARMCC, and the no-diff test that guards it.
- Whether the flexible path adopts the envelope, and the host reader's dispatch role.
- The armcc gate's lane, warning policy and skip behaviour.
- The test-collection fix in both `pytest.ini` and `tasks.py`.

Non-negotiables to state as constraints in the spec, because an agent that does not know
them will break something expensive:

- Wave 1 changes no on-wire byte. The no-diff and round-trip tests are meaningful only
  because of that.
- `SUBSCRIBE_ADDR_SRAM_LO/HI` stay undefined in `JX_FLY.uvprojx`.
- Never invoke UV4 without `<pMon>` neutralisation; go through `rebuild_and_flash`.
- `OBJ/JX_FLY.axf` must match the flashed image.
- No flash and no target interaction without an explicit operator go-ahead in chat.
- USART3 command dispatch stays unwired. Do not add an inbound parser to the radio.
- Use the `/codebase-design` vocabulary exactly — module, interface, implementation, depth,
  deep, shallow, seam, adapter, leverage, locality. Not component, service, API, boundary,
  layer, wrapper.
- The two drifts this work must make impossible rather than merely repair: VOFA's 13 names
  against Frame A's 16 keys, and `diag_telemetry.py`'s proto 13 against firmware's 14.

Two things to check before writing, both of which may have moved:

- The suite total. 487 passing as of 2026-07-30, before the comm lane was collected.
- Whether `flight_analysis/` still sits at the repo root rather than under
  `ground_station/`. It does as of 2026-07-30, and it is why nothing imports it — but that
  belongs to the wave-3 analysis effort, not here. Do not fix it in this spec.
