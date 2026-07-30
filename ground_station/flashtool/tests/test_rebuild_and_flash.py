"""The pipeline must fail closed at every stage, and never leave a lie on disk.

The dangerous outcome is not "the flash failed" -- it is "the flash failed and
OBJ/JX_FLY.axf now describes an image the drone is not running", because every
address livewatch and the safety gates resolve comes from that file.
"""
import pytest

from ground_station.flashtool import rebuild_and_flash as rf


@pytest.fixture
def rig(monkeypatch, tmp_path):
    """Neutralise every real-world effect; record what the pipeline decided."""
    calls = {"restored": 0, "flashed": 0, "built": 0}

    monkeypatch.setattr(rf, "uv4_resident", lambda: False)
    monkeypatch.setattr(rf, "snapshot_artifacts", lambda: True)
    monkeypatch.setattr(rf, "restore_artifacts",
                        lambda: calls.__setitem__("restored", calls["restored"] + 1))
    monkeypatch.setattr(rf, "target_alive", lambda *a, **k: True)
    monkeypatch.setattr(rf, "arm_status", lambda elf: rf.DISARMED)
    monkeypatch.setattr(rf.shutil, "rmtree", lambda *a, **k: None)
    monkeypatch.setattr(rf.time, "sleep", lambda *a: None)

    def ok_build(rebuild=True, timeout=900):
        calls["built"] += 1
        return 1, "0 Error(s), 74 Warning(s).", True
    monkeypatch.setattr(rf, "build", ok_build)

    def ok_flash(attempts=3, timeout=600):
        calls["flashed"] += 1
        return True, "Programming Done. Verify OK."
    monkeypatch.setattr(rf, "flash", ok_flash)

    # The ARM check only runs when the snapshot ELF is on disk.
    monkeypatch.setattr(rf, "SNAPSHOT", tmp_path)
    (tmp_path / "JX_FLY.axf").write_bytes(b"elf")
    return calls


# ---- consent -------------------------------------------------------------

def test_without_yes_it_builds_and_stops(rig):
    assert rf.main([]) == 0
    assert rig["built"] == 1
    assert rig["flashed"] == 0


def test_a_build_without_flash_restores_the_flashed_artifacts(rig):
    """Otherwise OBJ/ holds new addresses while the drone runs the old image."""
    rf.main([])
    assert rig["restored"] == 1


def test_with_yes_it_flashes(rig):
    assert rf.main(["--yes"]) == 0
    assert rig["flashed"] == 1


# ---- refusals ------------------------------------------------------------

def test_a_resident_uv4_stops_everything(rig, monkeypatch):
    monkeypatch.setattr(rf, "uv4_resident", lambda: True)
    assert rf.main(["--yes"]) == 2
    assert rig["built"] == 0


def test_a_failed_build_never_flashes_and_restores(rig, monkeypatch):
    monkeypatch.setattr(rf, "build", lambda **k: (2, "1 Error(s)", True))
    assert rf.main(["--yes"]) == 3
    assert rig["flashed"] == 0
    assert rig["restored"] == 1


def test_an_unrestored_uvoptx_blocks_the_flash(rig, monkeypatch):
    """A mangled uvoptx would break the operator's GUI debug session."""
    monkeypatch.setattr(rf, "build", lambda **k: (1, "0 Error(s)", False))
    assert rf.main(["--yes"]) == 4
    assert rig["flashed"] == 0


def test_a_dark_target_is_not_flashed(rig, monkeypatch):
    monkeypatch.setattr(rf, "target_alive", lambda *a, **k: False)
    assert rf.main(["--yes"]) == 5
    assert rig["flashed"] == 0


def test_an_armed_drone_is_not_flashed(rig, monkeypatch):
    monkeypatch.setattr(rf, "arm_status", lambda elf: 1)
    assert rf.main(["--yes"]) == 6
    assert rig["flashed"] == 0


def test_an_unreadable_arm_status_is_not_assumed_disarmed(rig, monkeypatch):
    def boom(elf):
        raise RuntimeError("probe busy")
    monkeypatch.setattr(rf, "arm_status", boom)
    assert rf.main(["--yes"]) == 6
    assert rig["flashed"] == 0


# ---- failure leaves disk honest -----------------------------------------

def test_a_failed_flash_restores_the_previous_artifacts(rig, monkeypatch):
    monkeypatch.setattr(rf, "flash", lambda **k: (False, "RDDI-DAP Error"))
    assert rf.main(["--yes"]) == 7
    assert rig["restored"] == 1


def test_a_target_that_does_not_come_back_is_reported(rig, monkeypatch):
    states = iter([True, False])
    monkeypatch.setattr(rf, "target_alive", lambda *a, **k: next(states))
    assert rf.main(["--yes"]) == 8


# ---- the retry that saved the session -----------------------------------

def test_flash_retries_a_transient_rddi_dap_failure(monkeypatch):
    results = iter([(2, "Erase Done.Programming Failed!RDDI-DAP Error"),
                    (0, "Programming Done. Verify OK.")])
    monkeypatch.setattr(rf.sf, "_run_uv4", lambda *a, **k: next(results))
    monkeypatch.setattr(rf.time, "sleep", lambda *a: None)
    ok, text = rf.flash(attempts=3)
    assert ok and "Verify OK" in text


def test_flash_gives_up_rather_than_looping_forever(monkeypatch):
    monkeypatch.setattr(rf.sf, "_run_uv4",
                        lambda *a, **k: (2, "Programming Failed!RDDI-DAP Error"))
    monkeypatch.setattr(rf.time, "sleep", lambda *a: None)
    ok, _ = rf.flash(attempts=3)
    assert ok is False
