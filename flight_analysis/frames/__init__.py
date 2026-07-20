"""Frame-type abstractions for different UAV configurations."""

from flight_analysis.frames.base import FrameConfig, FrameRegistry
from flight_analysis.frames.quad import QuadFrame
from flight_analysis.frames.hex import HexFrame
from flight_analysis.frames.custom import CustomFrame

# Register default frame types
FrameRegistry.register("quad", QuadFrame)
FrameRegistry.register("hex", HexFrame)


def get_frame(frame_type: str) -> FrameConfig:
    """Get a frame configuration by type.

    Args:
        frame_type: Frame type name ('quad', 'hex', 'custom').

    Returns:
        FrameConfig instance.

    Raises:
        ValueError: If frame type is unknown.
    """
    frame_class = FrameRegistry.get(frame_type)
    if frame_class is None:
        raise ValueError(f"Unknown frame type: {frame_type}. "
                        f"Available: {FrameRegistry.available()}")
    return frame_class()


__all__ = [
    "FrameConfig",
    "FrameRegistry",
    "QuadFrame",
    "HexFrame",
    "CustomFrame",
    "get_frame",
]
