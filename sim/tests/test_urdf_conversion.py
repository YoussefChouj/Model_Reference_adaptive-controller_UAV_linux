"""URDF→SDF conversion regression tests (spec 4c)."""
from __future__ import annotations

from pathlib import Path

import pytest

from sim.urdf_conversion import (
    URDFConversionError,
    convert_urdf_to_sdf,
    _inject_imu,
)


def _write_minimal_urdf_with_body_link(urdf_path: Path, body_name: str) -> None:
    """Write a minimal URDF whose body link name is configurable."""
    urdf_path.parent.mkdir(parents=True, exist_ok=True)
    urdf_path.write_text(
        f"""<?xml version=\"1.0\"?>
<robot name=\"jx_fly\">
  <link name=\"{body_name}\">
    <inertial>
      <origin xyz=\"0 0 0\" rpy=\"0 0 0\"/>
      <mass value=\"1.0\"/>
      <inertia ixx=\"0.01\" iyy=\"0.01\" izz=\"0.01\"
               ixy=\"0\" ixz=\"0\" iyz=\"0\"/>
    </inertial>
  </link>
</robot>
""",
        encoding="utf-8",
    )


def test_convert_urdf_to_sdf_injects_imu(tmp_path):
    """The happy path: a URDF with the canonical body link name produces
    a converted SDF that carries the canonical IMU sensor and topic."""
    urdf = tmp_path / "in" / "jx_fly.urdf"
    sdf = tmp_path / "out" / "jx_fly_model.sdf"
    _write_minimal_urdf_with_body_link(urdf, "jx_fly_body")
    convert_urdf_to_sdf(urdf, sdf, use_gz_binary=False)
    text = sdf.read_text(encoding="utf-8")
    assert '<sensor name="jx_fly_imu"' in text
    assert '<topic>/world/jx_fly/imu</topic>' in text


def test_convert_urdf_to_sdf_raises_when_body_link_renamed(tmp_path):
    """If the URDF body link name drifts (and the IMU cannot be
    injected), ``convert_urdf_to_sdf`` must raise
    ``URDFConversionError`` instead of silently producing a world
    without an IMU."""
    urdf = tmp_path / "in" / "jx_fly.urdf"
    sdf = tmp_path / "out" / "jx_fly_model.sdf"
    _write_minimal_urdf_with_body_link(urdf, "renamed_body")
    with pytest.raises(URDFConversionError, match="IMU sensor was not injected"):
        convert_urdf_to_sdf(urdf, sdf, use_gz_binary=False)


def test_inject_imu_substitutes_only_on_match(tmp_path):
    """The injector itself leaves non-matching SDF text untouched so
    the structural assertion in ``convert_urdf_to_sdf`` is the one
    that surfaces the failure to the operator."""
    source = tmp_path / "source.sdf"
    target = tmp_path / "target.sdf"
    source.write_text('<sdf><model><link name="other"/></model></sdf>', encoding="utf-8")
    _inject_imu(source, target)
    assert '<sensor name="jx_fly_imu"' not in target.read_text(encoding="utf-8")