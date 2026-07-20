"""Frame base class and registry for UAV configurations.

Provides abstraction for different frame types (quad, hex, custom)
with their physical properties and control allocation matrices.
"""

from __future__ import annotations

import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Type
from dataclasses import dataclass, field


@dataclass
class FrameConfig(ABC):
    """Base configuration for UAV frame types."""

    # Physical properties
    num_motors: int = 4
    num_arms: int = 4
    arm_length: float = 0.1  # meters

    # Motor configuration
    motor_layout: str = "X"  # 'X' or '+'
    motor_directions: List[int] = field(default_factory=lambda: [1, -1, 1, -1])

    # Mixer scales (control output to motor command)
    mixer_scales: Dict[str, float] = field(default_factory=lambda: {
        "pitch": 1170.0,
        "roll": 1170.0,
        "yaw": 1872.0,
        "z": 222.0
    })

    # Expected dynamics
    natural_frequency: Dict[str, float] = field(default_factory=lambda: {
        "pitch": 5.0,  # Hz
        "roll": 5.0,
        "yaw": 3.0,
        "z": 2.0
    })

    # Physical constants
    mass: float = 0.8  # kg
    ixx: float = 0.004  # kg*m^2
    iyy: float = 0.004
    izz: float = 0.007

    @property
    @abstractmethod
    def frame_type(self) -> str:
        """Return the frame type identifier."""
        pass

    def get_mixer_scale(self, axis: str) -> float:
        """Get mixer scale for an axis."""
        return self.mixer_scales.get(axis, 1000.0)

    def get_axis_motors(self, axis: str) -> List[int]:
        """Get motor indices that contribute to an axis."""
        if self.num_motors == 4:
            if axis == "pitch":
                return [0, 2] if self.motor_layout == "X" else [1, 3]
            elif axis == "roll":
                return [1, 3] if self.motor_layout == "X" else [0, 2]
            elif axis == "yaw":
                return [0, 1, 2, 3]  # All motors
            elif axis == "z":
                return [0, 1, 2, 3]  # All motors
        elif self.num_motors == 6:
            if axis == "pitch":
                return [1, 3] if self.motor_layout == "X" else [0, 3]
            elif axis == "roll":
                return [2, 4] if self.motor_layout == "X" else [1, 4]
            elif axis == "yaw":
                return list(range(6))
            elif axis == "z":
                return list(range(6))
        return list(range(self.num_motors))

    def get_arm_angles(self) -> List[float]:
        """Get arm angles in radians."""
        angles = []
        for i in range(self.num_arms):
            base_angle = 2 * np.pi * i / self.num_arms
            # Add 45-degree offset for X configuration
            if self.motor_layout == "X":
                base_angle += np.pi / 4
            angles.append(float(base_angle))
        return angles

    def get_allocation_matrix(self) -> np.ndarray:
        """Get the control allocation matrix.

        Maps [thrust, roll, pitch, yaw] to motor outputs.

        Returns:
            2D numpy array of shape (num_motors, 4)
        """
        n = self.num_motors
        alloc = np.zeros((n, 4))

        # Extract arm parameters
        k_thrust = 1.0  # Thrust coefficient
        k_moment = 1.0 / self.arm_length  # Moment coefficient

        arm_angles = self.get_arm_angles()

        for i in range(n):
            angle = arm_angles[i]

            # Thrust contribution (same for all motors)
            alloc[i, 0] = k_thrust

            # Roll moment (about X axis in body frame)
            # Positive roll = right side down = motors on left produce more thrust
            alloc[i, 1] = -np.sin(angle) * k_moment * self.motor_directions[i]

            # Pitch moment (about Y axis in body frame)
            # Positive pitch = nose down = motors on tail produce more thrust
            alloc[i, 2] = np.cos(angle) * k_moment * self.motor_directions[i]

            # Yaw moment (about Z axis)
            # Produced by motor drag (opposite to spin direction)
            alloc[i, 3] = -self.motor_directions[i] * 0.1  # Small coefficient

        return alloc

    def get_control_to_physical(
        self,
        axis: str,
        mixer_scale: float
    ) -> Tuple[float, str]:
        """Get physical conversion for an axis.

        Args:
            axis: Control axis name.
            mixer_scale: Mixer scale value from telemetry.

        Returns:
            Tuple of (conversion_factor, unit_string).
        """
        if axis in ["pitch", "roll", "yaw"]:
            # Angular rate control, deg/s
            return (1.0, "deg/s")
        elif axis == "z":
            # Altitude rate, m/s
            return (1.0, "m/s")
        elif axis.startswith("gyro"):
            # Gyro rate, deg/s
            return (1.0, "deg/s")
        elif axis in ["locx", "locy"]:
            # Position, cm
            return (1.0, "cm")
        elif axis in ["locxs", "locys"]:
            # Velocity, cm/s
            return (1.0, "cm/s")
        elif axis == "z_pos":
            # Altitude, m
            return (1.0, "m")
        return (1.0, "units")


class FrameRegistry:
    """Registry for frame type configurations."""

    _frames: Dict[str, Type[FrameConfig]] = {}

    @classmethod
    def register(cls, name: str, frame_class: Type[FrameConfig]) -> None:
        """Register a frame type."""
        cls._frames[name] = frame_class

    @classmethod
    def get(cls, name: str) -> Optional[Type[FrameConfig]]:
        """Get a frame type by name."""
        return cls._frames.get(name)

    @classmethod
    def available(cls) -> List[str]:
        """List available frame types."""
        return list(cls._frames.keys())


def convert_control_to_torque(
    control_output: np.ndarray,
    mixer_scale: float,
    axis: str
) -> np.ndarray:
    """Convert control output to physical torque.

    Args:
        control_output: Raw control output values.
        mixer_scale: Mixer scale for this axis.
        axis: Control axis name.

    Returns:
        Torque values in appropriate physical units.
    """
    if axis in ["pitch", "roll", "yaw"]:
        # Angular acceleration, deg/s^2 (approximately)
        return control_output * mixer_scale / 1000.0
    elif axis == "z":
        # Vertical acceleration, m/s^2
        return control_output * mixer_scale / 100.0
    return control_output


def convert_control_to_force(
    control_output: np.ndarray,
    mixer_scale: float,
    axis: str
) -> np.ndarray:
    """Convert control output to physical force.

    Args:
        control_output: Raw control output values.
        mixer_scale: Mixer scale for this axis.
        axis: Control axis name.

    Returns:
        Force values in Newtons.
    """
    if axis == "z":
        # Vertical force, N
        return control_output * mixer_scale * 0.01  # Approximate
    return control_output * mixer_scale * 0.001
