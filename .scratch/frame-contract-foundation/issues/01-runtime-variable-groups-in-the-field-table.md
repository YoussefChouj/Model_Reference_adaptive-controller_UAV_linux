# How does the field table express runtime-variable repeated groups?

Type: grilling
Status: closed — out of scope (destination redrawn 2026-07-31)
Assignee: Youssef

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

## Resolution (2026-07-31) — ruled out of scope

**The question dissolves with its subject.** The operator's stated purpose for the link is
that it must absorb additions and subtractions as the controller evolves — new parameters,
a different controller, eventually neural networks in the adaptive layer. Measured against
that purpose the fixed frames cannot be the vehicle, so a byte-layout table generating
firmware and host decoders for them is work on frames that are being deleted. The
destination was redrawn the same day; see the map. **No field table will be built.**

The investigation still produced durable facts. They outlive the ticket and the new map
depends on several of them.

### The downlink envelope is 6 bytes, not 5 — the map's Notes were wrong

```
0xAA 0xBB | TYPE | LEN_HI | LEN_LO | BYTE5 | payload | CRC
```

**Byte 5 is a polymorphic, type-specific header slot**, covered by CRC on both families,
and `API/subscribe.h`'s pinned layout labels it `MAX_NUM_BASIS` even where it means
something else entirely:

| frame | byte 5 holds | site |
| --- | --- | --- |
| fixed A / B / C / ID / bench / OF | `MAX_NUM_BASIS` | `TASK/send_data.c:604, 654, 732, 822, 968`; `s_frame_c_buf[5]` at 881 |
| `0x07` reply, `0x7F` error | tuple count / echo of requested count | `API/subscribe.c:240, 301` |
| `0x08` schema | `n_ranges` | `API/subscribe.c:566` |
| `0x09+slot` data | **`st->seq`** — a sequence number, not a count | `API/subscribe.c:618` |

Any future envelope work must treat byte 5 as opaque. An envelope that interprets it as a
basis count cannot carry the data frame's sequence number.

### `MAX_NUM_BASIS` is compile-time, not runtime — the ticket's premise was wrong

`API/mrac.h:80-96` makes it a `#define` selected by two research flags:

| `USE_STRUCTURED_UNCERTAINTY` | `INCLUDE_CONTROL_IN_REGRESSOR` | `MAX_NUM_BASIS` |
| --- | --- | --- |
| 1 | 1 (current build) | `NUM_BASIS + 2` = **6** |
| 1 | 0 | `NUM_BASIS` = 4 |
| 0 | 1 | `2*NUM_BASIS + 2` = 10 |
| 0 | 0 | `2*NUM_BASIS` = 8 |

It is constant for any single flashed image. It travels on the wire so a host of unknown
vintage can decode a firmware of unknown vintage — not because it varies in flight. Any
consumer must resolve it from the header or the wire, **never** copy the number.

### A fourth un-sourced copy of that number exists

`ground_station/comm/serial_bridge.py:376` defaults `_last_max_num_basis = 8`, and
`TASK/send_data.c:445` sizes its buffer "@ MAX_NUM_BASIS=8". The real value is 6. Only a
pre-first-frame default, but `get_last_max_num_basis()` feeds the dashboard, so a stale 8
is observable. Folded into the live-drift repair ticket.

### Frame B is 4 axes — confirmed on both sides

Firmware `TASK/send_data.c:963` computes `4 * (MAX_NUM_BASIS + 2) + 36`; host
`serial_bridge.py:776` computes the identical expression. The `_unpack_frame_b` comment at
`serial_bridge.py:705` claiming "3 axes ... total_floats = 3N+42" is stale documentation,
exactly as the map recorded. The code is right; the comment is wrong. It should be deleted
when the fixed-frame decoders are retired, not repaired in place.

### Why the fixed frames cannot carry the stated purpose

- **Byte 5 is one byte.** The repeat count caps at 255, with no spare header room to widen
  it without changing every frame on the wire.
- **The link is already over budget.** UART5 runs 11677 B/s against an 11520 B/s cap —
  101%. Frame B alone is 305 B x 16.3 Hz ~= 4971 B/s, 43% of the whole downlink. Going
  from 6 weights per axis to 32 adds ~416 B per frame ~= 6800 B/s. It does not fit at any
  rate worth having.
