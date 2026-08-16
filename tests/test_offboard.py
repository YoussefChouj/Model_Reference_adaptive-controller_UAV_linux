"""Tests for ground_station.offboard.

All MAVSDK calls are stubbed so these run without hardware.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ground_station.offboard import (
    OffboardController,
    _HEARTBEAT_PERIOD_S,
)


# ---------------------------------------------------------------------------
# Stub helpers
# ---------------------------------------------------------------------------

def _make_stub_system():
    """Return a System that records all method calls."""
    system = MagicMock()
    system.connect = AsyncMock()
    system.action = MagicMock()
    system.action.arm = AsyncMock()
    system.action.disarm = AsyncMock()
    system.action.land = AsyncMock()
    system.offboard = MagicMock()
    system.offboard.start = AsyncMock()
    system.offboard.stop = AsyncMock()
    system.offboard.set_position_ned = AsyncMock()
    system.offboard.set_velocity_body = AsyncMock()

    # Connection state iterator: immediately yields connected state.
    async def _conn_state():
        state = MagicMock()
        state.is_connected = True
        yield state

    system.core = MagicMock()
    system.core.connection_state = _conn_state
    return system


def _make_stub_system_not_connected():
    """Connection state iterator hangs (never yields) so the timeout fires.

    asyncio.wait_for cancels the underlying task after the deadline.
    The task raises CancelledError when cancelled mid-iteration, which
    asyncio.wait_for re-raises as asyncio.TimeoutError.
    """

    async def _conn_state():
        # Never yield — the task hangs here until CancelledError.
        await asyncio.sleep(3600)
        yield  # unreachable, makes this an async generator

    system = MagicMock()
    system.connect = AsyncMock()
    system.core = MagicMock()
    system.core.connection_state = _conn_state
    return system


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_connect_uses_default_uri():
    """connect() defaults to serial:///dev/ttyUSB0:921600."""
    import ground_station.offboard as ob_mod

    ctrl = OffboardController()
    assert ctrl._uri == "serial:///dev/ttyUSB0:921600"

    stub = _make_stub_system()
    with patch.object(ob_mod, "System", return_value=stub):
        await ctrl.connect()
        assert stub.connect.await_count == 1


@pytest.mark.anyio
async def test_connect_custom_uri():
    """connect() passes a custom URI through to MAVSDK System."""
    custom = "serial:///dev/ttyACM0:57600"
    ctrl = OffboardController(mavsdk_uri=custom)

    stub = _make_stub_system()
    import ground_station.offboard as ob_mod
    with patch.object(ob_mod, "System", return_value=stub):
        await ctrl.connect()
        stub.connect.assert_awaited_once_with(system_address=custom)


@pytest.mark.anyio
async def test_connect_timeout():
    """connect() raises asyncio.TimeoutError when no heartbeat arrives."""
    ctrl = OffboardController()

    stub = _make_stub_system_not_connected()
    import ground_station.offboard as ob_mod
    with patch.object(ob_mod, "System", return_value=stub):
        with pytest.raises(asyncio.TimeoutError):
            await ctrl.connect(timeout_s=0.05)


@pytest.mark.anyio
async def test_start_offboard_calls_offboard_start():
    """start_offboard() calls offboard.start() on the system."""
    ctrl = OffboardController()
    stub = _make_stub_system()
    import ground_station.offboard as ob_mod
    with patch.object(ob_mod, "System", return_value=stub):
        await ctrl.connect()
        await ctrl.start_offboard()
        stub.offboard.start.assert_awaited_once()


@pytest.mark.anyio
async def test_set_position_ned_emits_correct_message():
    """set_position_ned() passes correct NED coords to MAVSDK.

    PositionNedYaw uses north_m/east_m/down_m/yaw_deg fields.
    """
    ctrl = OffboardController()
    stub = _make_stub_system()
    import ground_station.offboard as ob_mod
    with patch.object(ob_mod, "System", return_value=stub):
        await ctrl.connect()
        await ctrl.set_position_ned(1.0, 2.0, 3.0, 90.0)

        stub.offboard.set_position_ned.assert_awaited_once()
        args, _ = stub.offboard.set_position_ned.await_args
        pos = args[0]
        assert pos.north_m == 1.0
        assert pos.east_m == 2.0
        assert pos.down_m == 3.0
        assert pos.yaw_deg == 90.0


@pytest.mark.anyio
async def test_takeoff_arms_and_ascends():
    """takeoff(altitude) arms and sends NED position with down_m = -altitude.

    NED z is positive down, so down_m=-altitude puts the drone above home.
    """
    ctrl = OffboardController()
    stub = _make_stub_system()
    import ground_station.offboard as ob_mod
    with patch.object(ob_mod, "System", return_value=stub):
        await ctrl.connect()
        await ctrl.start_offboard()  # sets _offboard_active = True
        await ctrl.takeoff(5.0)

        stub.action.arm.assert_awaited_once()
        stub.offboard.set_position_ned.assert_awaited()
        last_call = stub.offboard.set_position_ned.await_args
        pos = last_call[0][0]
        assert pos.north_m == 0.0
        assert pos.east_m == 0.0
        assert pos.down_m == -5.0
        assert pos.yaw_deg == 0.0


@pytest.mark.anyio
async def test_heartbeat_runs_while_offboard():
    """The heartbeat task fires set_velocity_body at roughly 20 Hz."""
    ctrl = OffboardController()
    stub = _make_stub_system()
    import ground_station.offboard as ob_mod
    with patch.object(ob_mod, "System", return_value=stub):
        await ctrl.connect()
        await ctrl.start_offboard()

        # Let the heartbeat run for ~0.15 s (≈3 ticks at 20 Hz).
        await asyncio.sleep(0.15)

        # Should have at least 2 set_velocity_body calls.
        assert stub.offboard.set_velocity_body.call_count >= 2


@pytest.mark.anyio
async def test_offboard_error_propagated():
    """An OffboardError from offboard.start() surfaces as a RuntimeError.

    OffboardError takes (result, origin); result needs a .result attribute.
    The controller re-raises it as a RuntimeError wrapping the error string.
    """
    from mavsdk.offboard import OffboardError, OffboardResult

    ctrl = OffboardController()
    stub = _make_stub_system()
    # Construct a fake result object that OffboardError.__init__ can use.
    fake_result = MagicMock()
    fake_result.result = OffboardResult.Result.COMMAND_DENIED
    stub.offboard.start = AsyncMock(
        side_effect=OffboardError(fake_result, "test")
    )
    import ground_station.offboard as ob_mod
    with patch.object(ob_mod, "System", return_value=stub):
        await ctrl.connect()
        with pytest.raises(RuntimeError, match="start_offboard failed"):
            await ctrl.start_offboard()


@pytest.mark.anyio
async def test_disarm_works_after_offboard_stop():
    """stop_offboard() followed by disarm() succeeds."""
    ctrl = OffboardController()
    stub = _make_stub_system()
    import ground_station.offboard as ob_mod
    with patch.object(ob_mod, "System", return_value=stub):
        await ctrl.connect()
        await ctrl.start_offboard()
        await ctrl.stop_offboard()
        await ctrl.disarm()

        stub.offboard.stop.assert_awaited_once()
        stub.action.disarm.assert_awaited_once()


@pytest.mark.anyio
async def test_disconnect_cancels_heartbeat():
    """disconnect() cancels the running heartbeat task."""
    ctrl = OffboardController()
    stub = _make_stub_system()
    import ground_station.offboard as ob_mod
    with patch.object(ob_mod, "System", return_value=stub):
        await ctrl.connect()
        await ctrl.start_offboard()
        assert ctrl._heartbeat_task is not None

        await ctrl.disconnect()
        assert ctrl._heartbeat_task is None


@pytest.mark.anyio
async def test_set_velocity_body_emits_correct_message():
    """set_velocity_body() passes correct body-frame values to MAVSDK.

    VelocityBodyYawspeed uses forward_m_s/right_m_s/down_m_s/yawspeed_deg_s.
    """
    ctrl = OffboardController()
    stub = _make_stub_system()
    import ground_station.offboard as ob_mod
    with patch.object(ob_mod, "System", return_value=stub):
        await ctrl.connect()
        await ctrl.start_offboard()
        await ctrl.set_velocity_body(1.0, -2.0, 0.5, 45.0)

        stub.offboard.set_velocity_body.assert_awaited()
        args, _ = stub.offboard.set_velocity_body.await_args
        vel = args[0]
        assert vel.forward_m_s == 1.0
        assert vel.right_m_s == -2.0
        assert vel.down_m_s == 0.5
        assert vel.yawspeed_deg_s == 45.0
