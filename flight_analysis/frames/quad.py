"""Quadcopter frame configuration."""

from flight_analysis.frames.base import FrameConfig


class QuadFrame(FrameConfig):
    """Configuration for standard quadcopter (4-motor) frame."""

    def __init__(
        self,
        layout: str = "X",  # 'X' or '+' configuration
        motor_directions: list = None,
        arm_length: float = 0.1,
        **kwargs
    ):
        super().__init__(
            num_motors=4,
            num_arms=4,
            motor_layout=layout,
            arm_length=arm_length,
            **kwargs
        )

        # Motor spin directions for yaw control
        if motor_directions:
            self.motor_directions = motor_directions
        elif layout == "X":
            # Standard X-frame: alternating CW/CCW
            self.motor_directions = [1, -1, 1, -1]
        else:
            # Plus frame
            self.motor_directions = [-1, 1, -1, 1]

    @property
    def frame_type(self) -> str:
        return "quad"

    # Mixer scales optimized for typical quad setup
    mixer_scales = {
        "pitch": 1170.0,
        "roll": 1170.0,
        "yaw": 1872.0,
        "z": 222.0
    }

    # Expected natural frequencies for well-tuned quad
    natural_frequency = {
        "pitch": 5.0,  # Hz
        "roll": 5.0,
        "yaw": 3.0,
        "z": 2.0
    }
