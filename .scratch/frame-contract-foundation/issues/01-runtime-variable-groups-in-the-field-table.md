# How does the field table express runtime-variable repeated groups?

Type: grilling
Status: open

## Question

The "fixed" frames are not fixed-length. Both `_unpack_frame_a` and `_unpack_frame_b`
take `max_num_basis` as their first parameter, because the per-axis MRAC `Theta` vectors
are sized by a value the firmware chooses at runtime and transmits alongside the data.
The host tracks it separately via `get_last_max_num_basis()`.

So the field table has to describe a layout whose length depends on a value carried on
the wire. That is the keystone decision for the whole table form: every other ticket on
this map assumes an answer to it.

What has to be settled:

- How a repeated group is declared — count from a named wire field, versus a fixed
  upper bound with a transmitted valid-count, versus something else.
- Whether the generated firmware header emits offsets at all, or only field identities
  plus a cursor-style writer, since a runtime count means offsets past the group are not
  compile-time constants.
- Whether the generated host module produces a decode function or a description the
  existing `_unpack_frame_*` methods consume.
- What the table says about `MAX_NUM_BASIS` itself. `API/mrac.h:85` defines it as 6
  (NUM_BASIS 4 plus 2 control terms), and `SymbolResolver` does **not** bounds-check
  array indices — `Theta[63]` resolves happily — so the bound must come from the header,
  not from a guess.
- Whether Frame B's per-axis layout is 4 axes or 3. The report established 4 is correct
  (the PID block decodes to real values at offset +128); the "3 axes" comment in
  `_unpack_frame_b` is stale documentation, not a bug. The table must pin 4 and the
  stale comment must go.

Evidence to start from: `ground_station/comm/serial_bridge.py` lines 600 (`_unpack_frame_a`)
and 702 (`_unpack_frame_b`); `API/mrac.h:85`; the layout built in
`Send_Groundstation_Telemetry_UART4()`.

Prefer the answer that keeps the generated firmware side free of computed offsets if
possible — the emitter currently writes sequentially, and a cursor matches what it
already does.
