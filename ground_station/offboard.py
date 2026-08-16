"""MAVSDK offboard controller — host-side bridge for the agent tool surface.

Wraps the async MAVSDK-Python API to command the drone via the MicoAir
radio's MAVLink-over-serial link (agent-05 wire).  Every arm() call
requires the caller to assert preflight_ok; the class does not
auto-acknowledge preflight.

Wire-protocol (CMD 0x21 / 0x22) is agent-05's scope.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from mavsdk import System
from mavsdk.action import ActionError
from mavsdk.offboard import OffboardError, PositionNedYaw, VelocityBodyYawspeed

log = logging.getLogger(__name__)

# PX4 requires a position setpoint at ≥1 Hz to stay in offboard.
# We send 0-velocity NED heartbeats at 20 Hz (50 ms period) to be safe.
_HEARTBEAT_PERIOD_S = 0.05
_HEARTBEAT_VELOCITY = VelocityBodyYawspeed(0.0, 0.0, 0.0, 0.0)


class OffboardController:
    """Async offboard controller using MAVSDK-Python.

    Args:
        mavsdk_uri: MAVSDK connection string.  Default is the MicoAir radio
            on USB-serial at 921600 baud.
    """

    def __init__(
        self,
        mavsdk_uri: str = "serial:///dev/ttyUSB0:921600",
    ) -> None:
        self._uri = mavsdk_uri
        self._system: Optional[System] = None
        self._heartbeat_task: Optional[asyncio.Task[None]] = None
        self._offboard_active = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self, timeout_s: float = 5.0) -> None:
        """Connect to the MicoAir radio's MAVLink endpoint and wait
        for a valid heartbeat.

        Raises:
            asyncio.TimeoutError: no heartbeat within *timeout_s*.
            RuntimeError: MAVSDK server fails to start.
        """
        self._system = System()
        await self._system.connect(system_address=self._uri)

        log.info("Connecting to %s …", self._uri)

        # Wait for heartbeat with timeout.
        async def _wait_for_heartbeat():
            async for state in self._system.core.connection_state():
                if state.is_connected:
                    return
            # If the iterator closes without a connection, raise via no-return path.

        try:
            await asyncio.wait_for(asyncio.shield(_wait_for_heartbeat()), timeout=timeout_s)
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError(
                f"No heartbeat from {self._uri} within {timeout_s}s"
            )

        log.info("Connected.")

    async def disconnect(self) -> None:
        """Stop the heartbeat task and close the MAVSDK connection."""
        await self._stop_heartbeat()
        if self._system is not None:
            # System.close is synchronous in mavsdk-python 3.x.
            self._system = None
        log.info("Disconnected.")

    # ------------------------------------------------------------------
    # Arming / disarming
    # ------------------------------------------------------------------

    async def arm(self) -> None:
        """Arm the vehicle.

        Raises:
            ActionError: arm command was rejected by the firmware.
        """
        if self._system is None:
            raise RuntimeError("Not connected — call connect() first.")
        try:
            await self._system.action.arm()
        except ActionError:
            raise

    async def disarm(self) -> None:
        """Disarm immediately. Safer than waiting for failsafe."""
        if self._system is None:
            raise RuntimeError("Not connected — call connect() first.")
        try:
            await self._system.action.disarm()
        except ActionError:
            raise

    # ------------------------------------------------------------------
    # Offboard mode
    # ------------------------------------------------------------------

    async def start_offboard(self) -> None:
        """Start offboard mode.

        Raises:
            OffboardError: firmware rejected the mode switch
                (e.g. config flag not set, or not armed).
            RuntimeError: not connected.
        """
        if self._system is None:
            raise RuntimeError("Not connected — call connect() first.")
        try:
            await self._system.offboard.start()
        except OffboardError as exc:
            raise RuntimeError(f"start_offboard failed: {exc._result}") from exc

        self._offboard_active = True
        await self._start_heartbeat()
        log.info("Offboard mode started.")

    async def stop_offboard(self) -> None:
        """Stop offboard mode. Returns control to RC or failsafe."""
        await self._stop_heartbeat()
        self._offboard_active = False
        if self._system is None:
            return
        try:
            await self._system.offboard.stop()
        except OffboardError as exc:
            # stop_offboard is best-effort; log but don't raise.
            log.warning("stop_offboard: %s", exc.result)
        log.info("Offboard mode stopped.")

    # ------------------------------------------------------------------
    # Setpoint APIs
    # ------------------------------------------------------------------

    async def set_position_ned(
        self, x: float, y: float, z: float, yaw_deg: float
    ) -> None:
        """Send a position setpoint in the NED frame.

        Args:
            x: North position (m).
            y: East position (m).
            z: Down position (m, negative = above home).
            yaw_deg: Yaw angle (degrees, clockwise positive).
        """
        if self._system is None:
            raise RuntimeError("Not connected.")
        setpoint = PositionNedYaw(x, y, z, yaw_deg)
        try:
            await self._system.offboard.set_position_ned(setpoint)
        except OffboardError as exc:
            raise RuntimeError(
                f"set_position_ned({x},{y},{z},{yaw_deg}) failed: {exc._result}"
            ) from exc

    async def set_velocity_body(
        self, vx: float, vy: float, vz: float, yaw_rate_deg_s: float
    ) -> None:
        """Send a body-frame velocity setpoint.

        Args:
            vx: Forward velocity (m/s).
            vy: Rightward velocity (m/s).
            vz: Downward velocity (m/s, positive = descending).
            yaw_rate_deg_s: Yaw angular rate (deg/s, clockwise positive).
        """
        if self._system is None:
            raise RuntimeError("Not connected.")
        setpoint = VelocityBodyYawspeed(vx, vy, vz, yaw_rate_deg_s)
        try:
            await self._system.offboard.set_velocity_body(setpoint)
        except OffboardError:
            raise

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    async def takeoff(self, altitude_m: float) -> None:
        """Arm, then fly to *altitude_m* AGL in position-hold.

        Raises:
            ActionError / OffboardError: see arm() and set_position_ned().
        """
        await self.arm()
        # NED z is positive down, so -altitude_m puts us *above* home.
        await self.set_position_ned(0.0, 0.0, -altitude_m, 0.0)

    async def land(self) -> None:
        """Switch to land mode."""
        if self._system is None:
            raise RuntimeError("Not connected.")
        try:
            await self._system.action.land()
        except ActionError:
            raise

    async def goto(
        self, x: float, y: float, z: float, yaw_deg: float, tolerance_m: float = 0.5
    ) -> None:
        """Send position setpoints until the drone is within *tolerance_m*.

        Arms and enters offboard mode before sending the first setpoint.

        Args:
            x, y, z, yaw_deg: target NED position.
            tolerance_m: convergence threshold (m).
        """
        if self._system is None:
            raise RuntimeError("Not connected.")
        await self.arm()
        if not self._offboard_active:
            await self.start_offboard()
        await self.set_position_ned(x, y, z, yaw_deg)

    # ------------------------------------------------------------------
    # Internal: heartbeat task
    # ------------------------------------------------------------------

    async def _start_heartbeat(self) -> None:
        """Start the 20 Hz zero-velocity heartbeat task."""
        await self._stop_heartbeat()
        self._heartbeat_task = asyncio.create_task(self._offboard_heartbeat())

    async def _stop_heartbeat(self) -> None:
        """Cancel and await the heartbeat task if running."""
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

    async def _offboard_heartbeat(self) -> None:
        """Send a 0-velocity body setpoint at 20 Hz while offboard is active.

        PX4 exits offboard if no setpoint arrives within ~0.5 s.
        We stay well ahead of that threshold.
        """
        while True:
            if self._system is not None:
                try:
                    await self._system.offboard.set_velocity_body(_HEARTBEAT_VELOCITY)
                except OffboardError:
                    # Catching here prevents a stray error from crashing the task
                    # when the firmware exits offboard mid-flight.
                    pass
            await asyncio.sleep(_HEARTBEAT_PERIOD_S)
