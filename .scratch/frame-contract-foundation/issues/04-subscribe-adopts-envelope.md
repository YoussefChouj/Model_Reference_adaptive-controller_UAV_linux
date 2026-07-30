# Does the flexible-telemetry path adopt the Frame envelope module in wave 1?

Type: grilling
Status: open

## Question

The downlink envelope — `0xAA 0xBB | TYPE | LEN_HI | LEN_LO | payload | CRC-trailer` — is
open-coded 6× in `send_data.c` (lines 502, 876 and the header block re-opened four more
times) and 4× in `API/subscribe.c` (lines 240, 296, 566, 613 — the `0x07` reply, the
`0x7F` error, the `0x08` schema and the `0x09+slot` data frame).

Ten sites, one layout. The deepening is obvious. The question is whether wave 1 touches
the four in `subscribe.c`.

Arguments for including them:
- Ten sites collapsing to one is the whole point; leaving four behind means the envelope
  module has two callers instead of one family and the duplication survives.
- `subscribe.c` already compiles on the host through `API/tests/test_subscribe_harness.c`,
  so the round-trip seam for those four is free.

Arguments against:
- The flexible path was flashed on 2026-07-29 and verified on the drone: 3 slots at
  20/10/5 Hz for 30 s, 0 dropped and 0 malformed on every slot. Wave 1 is supposed to be
  behaviour-preserving, and this is working code with a measured result behind it.
- Protocol v2 (source timestamp plus CRC16-CCITT) is flashed but **has never been
  exercised against the running firmware**. Refactoring an unverified-on-hardware path
  makes the eventual verification ambiguous: a failure would not distinguish a v2 bug
  from a refactor bug.
- The CRC policy differs — the `0x09+slot` data frames use CRC16-CCITT (XModem, big-endian)
  while `0x08` and `0x7F` keep CRC8 XOR, deliberately. Absorbing both widens the
  envelope's interface, which is the opposite of deepening.

If the answer is no, say explicitly whether it becomes wave 2 or stays out of scope.

If the answer is yes, the sequencing constraint is that a v2 stream should be run against
the current firmware **first**, so there is a known-good baseline to compare against.

Recommendation to argue against: not in wave 1. Verify v2 on hardware, then adopt the
envelope in wave 2 with a real baseline to diff against.
