# Give the comm tests a home that the runners actually collect

Type: task
Status: open

## Question

Nothing to decide about the wire here — this is the mechanical gap that let the drift ship,
and the drift-detection tests from this map need somewhere to live that runs.

`ground_station/comm/` is in **neither** runner:

`pytest.ini` testpaths — flashtool/tests, build_budget/tests, livewatch/tests, gui/tests,
sim/tests, flight_analysis/tests, sil_gate/tests.

`tasks.py` LANES — livewatch, gui, sim, flight, sil, flashtool, budget.

So `ground_station/comm/test_frame_a_v13_contract.py` has never run in the normal suite,
including its two `GS_PROTO_VERSION == 14` assertions — which are exactly what would have
caught `diag_telemetry.py` sitting at 13. Commit `1875706` closed the same gap for the
flashtool and budget lanes and missed this one.

The work:

- Decide between moving the loose test file into a new `ground_station/comm/tests/`
  directory — matching every other lane in the repo, which is the convention — versus
  adding `ground_station/comm` to testpaths and leaving tests loose.
- Add the path to `pytest.ini` testpaths **and** to `tasks.py` LANES. Both. The two runners
  drifting apart is what produced this in the first place.
- Confirm the file passes once collected. It was repaired on 2026-07-30 (it had been
  asserting through the staleness guard after a 0.5 s sleep and now reads
  `_last_telemetry_*` directly), but it has still never run under the real runner.
- Report the new suite total. It was 487 passing on 2026-07-30 before this file was
  collected.

Recommendation: move to `ground_station/comm/tests/`, because a convention that holds
everywhere except one directory is how the next agent misses the next lane.
