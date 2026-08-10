---
session: operator-decisions
status: active
updated: 2026-08-09
superseded_by: null
supersedes: null
---

# Operator decisions — checked off as resolved

These are decisions that require your input, your action at the bench, or your confirmation before the agent closes them. The agent references this file and updates the checkboxes when you declare them resolved.

The agent should also append new decisions here when it surfaces a choice that requires you — not just carry it in Session State.

## In-flight decisions

- [ ] **Re-measure the ladder in flight.** Re-run the TX ring ladder with the drone airborne. Watch `UA3TxDrops` / `UA3TxPeak` (ring at 97 % occupancy on top rung). Real operating point (444 B) has 2.5× headroom. Pass: 0.00 % loss at 90363 B/s confirmed aloft.
- [ ] **Re-verify the stream aloft.** Run `stream_log.py --transport usart3` during the same flight. This is the thesis logging path. Pass: 0 drops, 0 malformed at 20/10/5 Hz confirmed aloft.

## Architecture decisions

- [x] **Wire USART3 command dispatch?** Wired 2026-08-09. Build green (`Code=81752`, +40 B vs previous build, 75 warnings unchanged), flashed, **dispatch verified end-to-end**: `UA3RxFrameCnt` advanced 3→5 across two sent `0xCC 0xDD` frames; `UA3RxLastLen=9` confirms the 9-byte frame landed in `UA3RxMailbox`; `Ctrler.locxPID.FB` / `locyPID.FB` collapsed from ±7 m to ±0.5 m after `CMD 0x10` over the radio. Mailbox bumped 11→96 B and DMA 22→256 B. **0xCC 0xDE subscribe requests remain UART5-only** — no reply DMA on USART3.
- [x] **Flip `USART3_THROUGHPUT_TEST` to 0?** Build green 2026-08-09 (`Code=81712`, same 75 warnings as the test build, OBJ restored post-build). Operator accepted the in-flight risk; **flashed, verified live**: 426/426 frames were 12 B attitude triples at 85.2 Hz. Zero throughput-ladder frames on the wire.
- [x] **Build the com0com bridge?** Superseded by native UDP (2026-08-10). All tools speak UDP directly to UDP 14550 (no virtual COM port, no com0com driver). Verified: `stream_log --transport usart3` captured 351 frames, 0.00 % loss. VOFA+ uses native UDP on ports 1347/1348. `scratchpad/micoair_vcom_bridge.py` deleted. `docs/telemetry-protocol.md` written.

## Bench setup decisions

- [ ] **Commit the uncommitted work?** All the 2026-08-09 TX ring + 0x21 stream work is uncommitted (524 tests green). The session is still open, so nothing is lost yet. Commit when you're done at the bench for the session.

## Decisions closed by the session (do not re-litigate)

- Baud > 921600 rejected — tested, do not retry.
- The "keep frames under ~700 B" rule is dead.
- Round-robin is obsolete — full MRAC state fits in one frame with 2.5× headroom.
- MRAC `What_lower_limit = 0` and `e_deadzone` are firmware quirks the simulation deliberately mirrors.

## How to add a new decision

When the agent surfaces a choice that requires you, it appends here:

```markdown
- [ ] **<short description>.** <why it needs you, what it unlocks or costs>.
```

When you resolve it, you or the agent checks the box and optionally appends a one-line resolution note.

Format: `sessions_summary/operator-decisions.md`