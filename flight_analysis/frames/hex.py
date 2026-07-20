"""Hexacopter frame configuration."""

from flight_analysis.frames.base import FrameConfig


class HexFrame(FrameConfig):
    """Configuration for standard hexacopter (6-motor) frame."""

    def __init__(
        self,
        layout: str = "X",  # 'X' or '+' configuration
        motor_directions: list = None,
        arm_length: float = 0.15,
        **kwargs
    ):
        super().__init__(
            num_motors=6,
            num_arms=6,
            motor_layout=layout,
            arm_length=arm_length,
            **kwargs
        )

        # Motor spin directions for yaw control
        if motor_directions:
            self.motor_directions = motor_directions
        elif layout == "X":
            # Standard X-frame hex: alternating CW/CCW, skip one
            self.motor_directions = [1, -1, 1, -1, 1, -1]
        else:
            # Plus frame
            self.motor_directions = [-1, 1, -1, 1, -1, 1]

    @property
    def frame_type(self) -> str:
        return "hex"

    # Mixer scales for hex (typically higher than quad due to more motors)
    mixer_scales = {
        "pitch": 1400.0,
        "roll": 1400.0,
        "yaw": 2200.0,
        "z": 300.0
    }

    # Expected natural frequencies for well-tuned hex
    natural_frequency = {
        "pitch": 4.5,
        "roll": 4.5,
        "yaw": 2.5,
        "z": 1.8
    }

    # Heavier than quad
    mass = 1.2
    ixx = 0.008
    iyy = 0.008
    izz = 0.012
