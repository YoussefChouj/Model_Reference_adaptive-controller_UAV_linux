"""Custom frame configuration."""

from flight_analysis.frames.base import FrameConfig


class CustomFrame(FrameConfig):
    """Configuration for custom UAV frame with user-defined parameters."""

    def __init__(
        self,
        num_motors: int = 4,
        num_arms: int = None,
        mixer_scales: dict = None,
        arm_length: float = 0.1,
        motor_layout: str = "X",
        motor_directions: list = None,
        natural_frequency: dict = None,
        mass: float = 0.8,
        ixx: float = 0.004,
        iyy: float = 0.004,
        izz: float = 0.007,
        **kwargs
    ):
        super().__init__(
            num_motors=num_motors,
            num_arms=num_arms if num_arms is not None else num_motors,
            arm_length=arm_length,
            motor_layout=motor_layout,
            **kwargs
        )

        # Set motor directions
        if motor_directions:
            self.motor_directions = motor_directions
        else:
            # Default: alternating for yaw control
            self.motor_directions = [1 if i % 2 == 0 else -1 for i in range(num_motors)]

        # Set mixer scales
        if mixer_scales:
            self.mixer_scales = mixer_scales
        else:
            # Default quad-like scales
            self.mixer_scales = {
                "pitch": 1170.0,
                "roll": 1170.0,
                "yaw": 1872.0,
                "z": 222.0
            }

        # Set natural frequencies
        if natural_frequency:
            self.natural_frequency = natural_frequency
        else:
            self.natural_frequency = {
                "pitch": 5.0,
                "roll": 5.0,
                "yaw": 3.0,
                "z": 2.0
            }

        # Physical parameters
        self.mass = mass
        self.ixx = ixx
        self.iyy = iyy
        self.izz = izz

    @property
    def frame_type(self) -> str:
        return "custom"

    def validate(self) -> list:
        """Validate frame configuration.

        Returns:
            List of validation warnings/errors.
        """
        issues = []

        # Check motor directions
        cw = sum(1 for d in self.motor_directions if d > 0)
        ccw = sum(1 for d in self.motor_directions if d < 0)

        if cw == ccw:
            issues.append("WARNING: Equal CW/CCW motors may result in no yaw authority")
        elif abs(cw - ccw) == 1:
            issues.append("INFO: Single extra motor spin direction provides minimal yaw control")

        # Check arm length
        if self.arm_length < 0.05:
            issues.append("WARNING: Very short arms may cause insufficient yaw authority")
        elif self.arm_length > 0.5:
            issues.append("INFO: Long arms provide good yaw authority but may affect agility")

        # Check mass
        if self.mass > 2.0:
            issues.append("WARNING: Heavy frame may require increased mixer scales")

        return issues
