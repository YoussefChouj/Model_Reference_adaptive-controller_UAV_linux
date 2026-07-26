"""Headless smoke test for the Live Log tab.

Exercises the new tab's widgets and callbacks without opening a real Dear PyGui
window. Pytest-shaped: a single test creates a context, builds the GUI body,
then drives the widgets directly to make sure:

  - the manifest combo populates from manifests.yaml
  - selecting a manifest fills doc + hz
  - "Check budget" resolves symbols, plans regions, and reports feasibility
  - "Verify ELF" runs and reports against the real ELF (catches the
    no-probe RuntimeError as designed)
  - ad-hoc vars override the manifest
  - UART5 selection uses its own transport and never silently substitutes SWD
  - bad var names surface as a UI error, not a crash

This is offline-ish: the Verify path opens a CMSIS-DAP session and reads
flash, which requires the probe. If the operator is on the bench with the
drone connected, it should pass; if not, the error must be displayed --
which is itself the assertion we want. So the test is not flaky against
hardware absence, just informative.

The no-fallback contract documented in the test_transport.py counterpart
applies here too: every higher callback layer (the dashboard's _livelog_*)
must also be free of `try: ... except: transport = SwdCmsisDap()` branches.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

import dearpygui.dearpygui as dpg  # noqa: E402

from ground_station.gui.dashboard import Dashboard  # noqa: E402


@pytest.fixture
def dash():
    dpg.create_context()
    d = Dashboard.__new__(Dashboard)
    d.repo_root = REPO / "ground_station"
    d._livelog_stop_event = None
    d._livelog_thread = None
    d._livelog_fh = None
    d._livelog_writer = None
    d._livelog_dir = d.repo_root / "logs" / "livewatch"
    d._livelog_dir.mkdir(parents=True, exist_ok=True)
    d._post_ui_call = lambda fn, *a, **kw: None
    d.connected = False
    d.bridge = None
    with dpg.window(label="test_livelog"):
        d._build_live_log_tab()
    yield d
    dpg.destroy_context()


def test_widgets_registered(dash):
    # tab_livelog itself is registered by _build_gui; this body test only
    # checks the inner widgets _build_live_log_tab created.
    for tag in (
        "combo_livelog_manifest",
        "combo_livelog_link",
        "txt_livelog_doc",
        "inp_livelog_hz",
        "inp_livelog_vars",
        "btn_livelog_start",
        "btn_livelog_stop",
        "txt_livelog_status",
        "txt_livelog_path",
    ):
        assert dpg.does_item_exist(tag), f"missing widget: {tag}"


def test_manifest_combo_populated(dash):
    items = dpg.get_item_configuration("combo_livelog_manifest")["items"]
    for name in ("ekf_ba_check", "ekf_vs_of", "of_drift", "pos_loop", "health"):
        assert name in items, f"manifest {name!r} not in combo: {items}"


def test_manifest_select_fills_doc_and_hz(dash):
    dash._on_livelog_manifest_select(None, "ekf_ba_check")
    doc = dpg.get_value("txt_livelog_doc")
    assert "b_a" in doc or "D5" in doc, f"unexpected doc: {doc[:120]!r}"
    assert dpg.get_value("inp_livelog_hz") == 20.0

    dash._on_livelog_manifest_select(None, "of_drift")
    assert dpg.get_value("inp_livelog_hz") == 50.0


def test_check_budget_offline(dash):
    dpg.set_value("combo_livelog_manifest", "of_drift")
    dpg.set_value("inp_livelog_hz", 50.0)
    dash._on_livelog_manifest_select(None, "of_drift")
    dash._livelog_check_budget()
    budget = dpg.get_value("txt_livelog_budget")
    assert "of_drift" in budget, f"unexpected budget: {budget!r}"
    assert "max" in budget, f"missing max Hz: {budget!r}"


def test_adhoc_vars_override_manifest(dash):
    dpg.set_value("inp_livelog_vars", "s_ekf.active s_ekf.nis")
    dash._livelog_check_budget()
    adhoc = dpg.get_value("txt_livelog_budget")
    assert "adhoc" in adhoc, f"adhoc budget wrong: {adhoc!r}"


def test_adhoc_bad_vars_surfaces_error(dash):
    dpg.set_value("inp_livelog_vars", "this_does_not_exist")
    dash._livelog_check_budget()
    err = dpg.get_value("txt_livelog_budget")
    assert "error" in err.lower(), f"bad vars didn't surface error: {err!r}"


def test_uart5_selection_has_no_swd_fallback(dash):
    dash._on_livelog_link_select(None, "Long-range (UART5)")
    dpg.set_value("combo_livelog_link", "Long-range (UART5)")
    transport = dash._livelog_transport()
    status = dpg.get_value("txt_livelog_status")
    assert transport.name == "uart5"
    assert "never fall back to SWD" in status
    assert "not wired" not in status


def test_uart5_refuses_when_bridge_connected(dash):
    """When the dashboard's SerialBridge holds the COM port, the UART5 path
    must refuse to open a duplicate serial.Serial and surface the message in
    the status box (which the existing _livelog_start catch writes to).
    """
    dpg.set_value("combo_livelog_link", "Long-range (UART5)")
    dash.connected = True
    dash.bridge = object()  # sentinel: any non-None bridge owned it
    from ground_station.livewatch.transport import LiveTransportError
    with pytest.raises(LiveTransportError, match="disconnect the dashboard"):
        dash._livelog_transport()


def test_uart5_dashboard_no_swd_fallback(dash, monkeypatch):
    """No SWD construction when the dashboard's UART5 path raises.

    Counters the no-fallback property at the dashboard layer -- in addition
    to the transport itself. If a higher callback ever substituted SWD on
    a UART5 timeout, this test would catch it.
    """
    from ground_station.livewatch.transport import (
        SwdCmsisDap, Uart5LongRange,
    )

    class CountingSwd(SwdCmsisDap):
        def __init__(self, *a, **kw):
            constructions.append(1)
            super().__init__(*a, **kw)

    class NoReplySerial:
        def __init__(self, *a, **kw):
            self.in_waiting = 0
            self.writes = []

        def write(self, data):
            self.writes.append(bytes(data))
            return len(data)

        def read(self, size=1):
            return b""

        def close(self):
            pass

    constructions = []
    monkeypatch.setattr(
        "ground_station.livewatch.transport.SwdCmsisDap", CountingSwd)

    # Inject a real Uart5LongRange that points at a NoReplySerial returning
    # no reply; the dashboard's "Check budget" must surface the timeout in
    # txt_livelog_budget and never construct an SwdCmsisDap along the way.
    dpg.set_value("combo_livelog_link", "Long-range (UART5)")
    dash._livelog_transport = lambda: Uart5LongRange(
        "COM42", timeout=0.001, serial_factory=NoReplySerial)
    dash._livelog_check_budget()
    budget = dpg.get_value("txt_livelog_budget")
    assert "no reply" in budget, f"expected timeout string in budget: {budget!r}"
    assert constructions == [], (
        "no-fallback contract violated: SwdCmsisDap was constructed"
    )


def test_elf_path_resolves(dash):
    elf = dash._livelog_current_elf()
    assert elf.name == "JX_FLY.axf"
    assert elf.parent.name == "OBJ"


def test_verify_elf_runs(dash, monkeypatch):
    # Keep this headless suite deterministic: simulate the documented no-probe
    # case rather than waiting for USB probe discovery on the test machine.
    from pyocd.core.helpers import ConnectHelper
    monkeypatch.setattr(ConnectHelper, "session_with_chosen_probe",
                        staticmethod(lambda **kwargs: None))
    dash._livelog_verify_elf()
    text = dpg.get_value("txt_livelog_verify")
    assert "no CMSIS-DAP probe" in text


if __name__ == "__main__":
    # Standalone smoke-runner so an operator can exercise the tab without
    # pytest. Useful when a recent dashboard edit needs a quick check.
    import os
    sys.exit(pytest.main([__file__, "-v", "-s"] if "-v" in os.sys.argv else [__file__, "-q"]))