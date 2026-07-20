"""Tests for frame-type abstraction layer."""

import pytest
import numpy as np
from pathlib import Path


class TestFrameBase:
    """Test suite for frame base class."""

    def test_frame_config_creation(self):
        """Test frame configuration creation."""
        from flight_analysis.frames.quad import QuadFrame
        
        quad = QuadFrame()
        assert quad.num_motors == 4
        assert quad.frame_type == "quad"

    def test_mixer_scale_retrieval(self):
        """Test mixer scale retrieval."""
        from flight_analysis.frames.quad import QuadFrame
        
        quad = QuadFrame()
        scale = quad.get_mixer_scale("pitch")
        assert scale > 0
        assert isinstance(scale, float)

    def test_axis_mapping(self):
        """Test axis to motor mapping."""
        from flight_analysis.frames.quad import QuadFrame
        
        quad = QuadFrame()
        # Quad X frame: pitch affects motors 0,2; roll affects motors 1,3
        pitch_motors = quad.get_axis_motors("pitch")
        roll_motors = quad.get_axis_motors("roll")
        
        assert len(pitch_motors) == 2
        assert len(roll_motors) == 2
        # Should be different motor pairs
        assert set(pitch_motors) != set(roll_motors)


class TestQuadFrame:
    """Test suite for quadcopter configuration."""

    def test_quad_frame_properties(self):
        """Test quad frame properties."""
        from flight_analysis.frames.quad import QuadFrame
        
        quad = QuadFrame()
        
        assert quad.frame_type == "quad"
        assert quad.num_motors == 4
        assert quad.num_arms == 4
        # Get arm angles dynamically
        arm_angles = quad.get_arm_angles()
        assert len(arm_angles) == 4

    def test_control_allocation(self):
        """Test control allocation matrix."""
        from flight_analysis.frames.quad import QuadFrame
        
        quad = QuadFrame()
        alloc = quad.get_allocation_matrix()
        
        # Should be 4x4 matrix (4 motors, 4 axes)
        assert alloc.shape == (4, 4)


class TestHexFrame:
    """Test suite for hexacopter configuration."""

    def test_hex_frame_properties(self):
        """Test hex frame properties."""
        from flight_analysis.frames.hex import HexFrame
        
        hex_frame = HexFrame()
        
        assert hex_frame.frame_type == "hex"
        assert hex_frame.num_motors == 6
        assert hex_frame.num_arms == 6


class TestCustomFrame:
    """Test suite for custom frame configuration."""

    def test_custom_frame_creation(self):
        """Test custom frame creation."""
        from flight_analysis.frames.custom import CustomFrame
        
        # Create a custom frame with specific parameters
        custom = CustomFrame(
            num_motors=8,
            mixer_scales={"pitch": 1000, "roll": 1000, "yaw": 1500, "z": 300},
            arm_length=0.15
        )
        
        assert custom.num_motors == 8
        assert custom.get_mixer_scale("pitch") == 1000

    def test_frame_registry(self):
        """Test frame type registration."""
        from flight_analysis.frames.base import FrameRegistry, FrameConfig
        
        # Register a custom frame type
        class TestFrame(FrameConfig):
            frame_type = "test"
            num_motors = 4
        
        FrameRegistry.register("test", TestFrame)
        
        # Should be able to retrieve it
        retrieved = FrameRegistry.get("test")
        assert retrieved is not None
        assert retrieved.frame_type == "test"


class TestFrameConversion:
    """Test suite for unit conversions with frame types."""

    @pytest.fixture
    def real_flight_csv(self):
        root = Path(__file__).parent.parent.parent
        return root / "ground_station" / "logs" / "flight_1784538359.csv"

    def test_control_effort_conversion(self, real_flight_csv):
        """Test control effort conversion to physical units."""
        if not real_flight_csv.exists():
            pytest.skip(f"Real flight log not found: {real_flight_csv}")
        
        from flight_analysis.core.loader import load_flight_csv
        from flight_analysis.frames.quad import QuadFrame
        from flight_analysis.frames.base import convert_control_to_torque
        
        data = load_flight_csv(str(real_flight_csv))
        
        quad = QuadFrame()
        
        # Get pitch control effort
        from flight_analysis.core.loader import get_signal
        u_tuple = get_signal(data, "pid.pitch.U")
        
        if u_tuple[0] is not None:
            u = np.array(u_tuple[1][:100])  # First 100 samples
            mixer_scale = quad.get_mixer_scale("pitch")
            
            # Convert to torque (simplified)
            torque = convert_control_to_torque(u, mixer_scale, "pitch")
            
            assert len(torque) == len(u)
            assert isinstance(torque[0], (int, float, np.floating))
