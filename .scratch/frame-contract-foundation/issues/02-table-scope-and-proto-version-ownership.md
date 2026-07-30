# Which fixed frames does the wave-1 table cover, and does it own GS_PROTO_VERSION?

Type: grilling
Status: open

## Question

Six fixed-frame decoders exist on the host, all in `ground_station/comm/serial_bridge.py`:

| decoder | line | frame |
| --- | --- | --- |
| `_unpack_frame_a` | 600 | `0x01` — attitude, PID, RC authority, OF hold, estimator ready |
| `_unpack_frame_b` | 702 | `0x02` — MRAC per-axis Theta, 305 B, the big one |
| `_unpack_frame_c` | 864 | `0x06` — body rates |
| `_unpack_frame_id` | 892 | `0x03` — SysID FSM state, 91 B |
| `_unpack_frame_bench` | 924 | bench characterisation |
| `_unpack_frame_of` | 959 | optical flow |

Plus two VOFA channel-name builders at `ground_station/gui/vofa_manager.py` lines 447 and
464, and `_get_stream_expected_channel_names` / `_repair_stream_config_channel_names`
at 636 and 642.

Two things to decide:

1. **Coverage.** A/B/C are live on every flight and carry the thesis signals. ID, bench
   and OF are narrower. Covering all six makes the table the whole truth; covering three
   ships sooner and leaves a second class of frame still open-coded — which is the exact
   condition that produced the current drift.

2. **Does the table own the protocol version?** Today `GS_PROTO_VERSION` lives in the
   host bridge and is restated in `ground_station/scripts/diag_telemetry.py:23`, which
   still says `FW_GS_PROTO_VERSION = 13` against firmware's 14. If the table owns the
   version and both sides read it from the generated output, that drift becomes
   structurally impossible rather than merely fixed once.

The two already-measured drifts this ticket must make impossible, not just repair:

- `_build_frame_a_channel_names` returns **13** names while `_unpack_frame_a` returns
  **16** keys, so every VOFA channel from index 13 onward has been mislabelled since
  Frame A gained `rc_authority` / `of_hold` / `estimator_ready`.
- `diag_telemetry.py` proto 13 versus firmware 14.

Also decide whether the table is the place `docs/interfaces.md`'s stale claim ("Frame A
fixed 37 bytes", "0x01 or 0x02") gets corrected, or whether documentation generation is
left in the fog for now.

Recommendation to argue against: cover all six. The narrow three leave the drift
mechanism alive in the frames nobody watches, which is where it survived last time.
