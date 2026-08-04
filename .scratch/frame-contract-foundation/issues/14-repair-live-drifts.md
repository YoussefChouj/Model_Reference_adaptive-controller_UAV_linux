# Repair the three live drifts now, independently of the migration

Type: task
Status: open

## Question

Nothing to decide. These are wrong **today**, they are small, and none of them should wait
on a migration that will take weeks. Split out of the two closed table-scope tickets so
they are not lost with them.

1. **VOFA channel names mislabelled since Frame A grew.**
   `_build_frame_a_channel_names` (`ground_station/gui/vofa_manager.py:447`) returns **13**
   names while `_unpack_frame_a` (`ground_station/comm/serial_bridge.py:600`) returns **16**
   keys. Frame A gained `rc_authority`, `of_hold` and `estimator_ready`; the decoder was
   updated and the name builder was not. Every VOFA channel from index 13 onward has been
   carrying the wrong label since. Any plot or log read off those channels is mislabelled,
   which is the silently-wrong-data failure mode, not a cosmetic one.

2. **`diag_telemetry.py` protocol version behind firmware.**
   `ground_station/scripts/diag_telemetry.py:23` sets `FW_GS_PROTO_VERSION = 13` against
   firmware's 14.

3. **A fourth un-sourced copy of `MAX_NUM_BASIS`.**
   `ground_station/comm/serial_bridge.py:376` defaults `_last_max_num_basis = 8` and
   `TASK/send_data.c:445` sizes its buffer "@ MAX_NUM_BASIS=8". The real value is **6**
   (`API/mrac.h:85`, `NUM_BASIS + 2`). It is only a pre-first-frame default, but
   `get_last_max_num_basis()` feeds the dashboard, so a stale 8 is observable before the
   first frame lands. Fix the host default; the firmware comment is a comment and can be
   corrected in place. Do not change `MAX_NUM_BASIS` itself.

Also correct while here, since it is the same class and costs nothing:
`_unpack_frame_b`'s comment at `serial_bridge.py:705` claims "3 axes ... total_floats =
3N+42". Both firmware (`TASK/send_data.c:963`) and host (`serial_bridge.py:776`) compute
`4 * (MAX_NUM_BASIS + 2) + 36`. **The code is right at 4 axes; the comment is wrong.**
Fix the comment only — the decode is correct and verified, with the PID block landing at
offset +128 and decoding to real values.

Constraints:

- **Host-side only for items 1 and 2** — no firmware change, no flash, no target
  interaction.
- Item 3's firmware half is a comment. Do not trigger a rebuild for it; fold it into
  whatever flash happens next, because a rebuild shifts RAM symbol addresses and
  `OBJ/JX_FLY.axf` must keep matching the flashed image.
- Land this **after** [Give the comm tests a home that the runners actually
  collect](07-collect-the-comm-tests.md) if the two are worked close together, so the
  repairs are covered by a suite that actually runs. `ground_station/comm/` is currently in
  neither `pytest.ini` testpaths nor `tasks.py` LANES, which is precisely why drift 2
  survived — `test_frame_a_v13_contract.py` carries two `GS_PROTO_VERSION == 14` assertions
  that have never executed.
- Add a regression test for item 1 asserting the name-builder length equals the decoder's
  key count. Repairing the count without pinning it invites the next addition to break it
  again.
