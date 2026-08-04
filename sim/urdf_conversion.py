"""URDF-to-SDF conversion helpers for spec 4c."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from sim.plant import CANONICAL_AIRFRAME
from sim.urdf import airframe_to_urdf, default_urdf_path


class URDFConversionError(RuntimeError):
    """Raised when URDF→SDF conversion fails a structural assertion.

    Used by ``convert_urdf_to_sdf`` to surface drift in the upstream
    ``gz sdf -p`` output (e.g. the IMU-injection target link renamed)
    rather than silently producing a sim world without the IMU.
    """


IMU_XML_TEMPLATE = """\
<sensor name="jx_fly_imu" type="imu">
  <topic>/world/jx_fly/imu</topic>
  <update_rate>1000</update_rate>
  <always_on>true</always_on>
  <imu>
    <angular_velocity>
      <x><noise type="gaussian"><mean>0</mean><stddev>0.0017</stddev></noise></x>
      <y><noise type="gaussian"><mean>0</mean><stddev>0.0017</stddev></noise></y>
      <z><noise type="gaussian"><mean>0</mean><stddev>0.0017</stddev></noise></z>
    </angular_velocity>
    <linear_acceleration>
      <x><noise type="gaussian"><mean>0</mean><stddev>0.0196</stddev></noise></x>
      <y><noise type="gaussian"><mean>0</mean><stddev>0.0196</stddev></noise></y>
      <z><noise type="gaussian"><mean>0</mean><stddev>0.0196</stddev></noise></z>
    </linear_acceleration>
  </imu>
</sensor>
"""


def _ensure_urdf(path: Path) -> Path:
    """Render the canonical URDF to disk if it is missing."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(airframe_to_urdf(CANONICAL_AIRFRAME), encoding="utf-8")
    return path


def _assert_imu_injected(sdf_text: str, source: str) -> None:
    """Assert the converted SDF actually carries the canonical IMU sensor.

    We deliberately do NOT just string-match the body link open tag in
    here -- that match is performed by ``_inject_imu``. After injection
    we still expect to find the canonical sensor name and topic, which
    is what downstream systems subscribe to. A failure here is fatal:
    raising ``URDFConversionError`` is the only safe behaviour, because
    a sim world without an IMU is the failure mode that crashes the
    bridge at runtime.
    """
    if '<sensor name="jx_fly_imu"' not in sdf_text:
        raise URDFConversionError(
            f"{source}: IMU sensor was not injected into the converted "
            "SDF (missing <sensor name=\"jx_fly_imu\"/>). Refusing to "
            "load a sim world without the canonical IMU."
        )
    if '<topic>/world/jx_fly/imu</topic>' not in sdf_text:
        raise URDFConversionError(
            f"{source}: IMU sensor was injected but lacks the "
            "canonical /world/jx_fly/imu topic. The bridge subscribes "
            "to that topic; anything else means the sim cannot publish "
            "an IMU stream the bridge can read."
        )


def convert_urdf_to_sdf(
    urdf_path: str | Path,
    output_sdf_path: str | Path,
    *,
    use_gz_binary: bool = True,
) -> Path:
    """Convert the URDF at ``urdf_path`` to SDF and write it to disk.

    Prefers ``gz sdf -p`` (the same pipeline Gazebo itself uses), but
    falls back to a Python-only conversion so the bridge can still be
    unit-tested on hosts without gz. The IMU sensor is injected by
    string-substitution on the converted SDF; this keeps the per-run
    simulator file deterministic and free of merge conflicts.

    After writing, this function asserts that the IMU sensor block
    (``<sensor name="jx_fly_imu">``) and its canonical topic
    (``/world/jx_fly/imu``) appear in the output. ``gz sdf -p``
    re-formats tags freely (attribute order, single vs double quotes,
    whitespace); a silent miss would surface as a runtime crash deep
    inside the bridge's IMU subscriber.
    """
    urdf = _ensure_urdf(Path(urdf_path))
    output = Path(output_sdf_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    source = "gz sdf -p" if use_gz_binary and shutil.which("gz") is not None else "python fixture"
    if use_gz_binary and shutil.which("gz") is not None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_sdf = Path(tmp) / "jx_fly.sdf"
            completed = subprocess.run(
                ["gz", "sdf", "-p", str(urdf)],
                capture_output=True, text=True, check=False,
            )
            if completed.returncode == 0 and completed.stdout.strip():
                tmp_sdf.write_text(completed.stdout, encoding="utf-8")
            else:
                tmp_sdf.write_text(_python_urdf_to_sdf(urdf), encoding="utf-8")
                source = "python fallback"
            _inject_imu(tmp_sdf, output)
            _assert_imu_injected(output.read_text(encoding="utf-8"), source)
            return output
    output.write_text(_python_urdf_to_sdf_with_imu(urdf), encoding="utf-8")
    _assert_imu_injected(output.read_text(encoding="utf-8"), source)
    return output


def _inject_imu(source_sdf: Path, target_sdf: Path) -> None:
    """Inject the IMU sensor block into the body link of the converted SDF.

    The substitution matches the canonical body link name produced by
    ``sim.urdf.airframe_to_urdf``. Any non-match is left untouched so
    the structural assertion in ``convert_urdf_to_sdf`` can fail fast
    instead of silently producing a sim world without an IMU.
    """
    text = source_sdf.read_text(encoding="utf-8")
    body_open = '<link name="jx_fly_body">'
    if body_open in text:
        text = text.replace(body_open, body_open + IMU_XML_TEMPLATE, 1)
    target_sdf.write_text(text, encoding="utf-8")


def _python_urdf_to_sdf(urdf_path: Path) -> str:
    """Python-only URDF→SDF translation (fixture for unit tests)."""
    root = ET.parse(urdf_path).getroot()
    sdf = ET.Element("sdf", attrib={"version": "1.9"})
    model = ET.SubElement(sdf, "model", attrib={"name": "jx_fly"})
    for link in root.findall("link"):
        link_name = link.attrib["name"]
        sdf_link = ET.SubElement(model, "link", attrib={"name": link_name})
        inertial = link.find("inertial")
        if inertial is not None:
            sdf_inertial = ET.SubElement(sdf_link, "inertial")
            origin = inertial.find("origin")
            if origin is not None:
                ET.SubElement(sdf_inertial, "pose").text = _origin_to_pose(origin)
            mass = inertial.find("mass")
            if mass is not None:
                ET.SubElement(sdf_inertial, "mass").text = mass.attrib["value"]
            inertia = inertial.find("inertia")
            if inertia is not None:
                sdf_inertia = ET.SubElement(sdf_inertial, "inertia")
                for key in ("ixx", "iyy", "izz", "ixy", "ixz", "iyz"):
                    ET.SubElement(sdf_inertia, key).text = inertia.attrib.get(key, "0")
        visual = link.find("visual")
        if visual is not None:
            ET.SubElement(sdf_link, "visual")
    return ET.tostring(sdf, encoding="unicode")


def _python_urdf_to_sdf_with_imu(urdf_path: Path) -> str:
    """Python-only URDF→SDF translation with the IMU sensor attached."""
    base = _python_urdf_to_sdf(urdf_path)
    body_open = '<link name="jx_fly_body">'
    if body_open in base:
        base = base.replace(body_open, body_open + IMU_XML_TEMPLATE, 1)
    return base


def _origin_to_pose(origin: ET.Element) -> str:
    xyz = origin.attrib.get("xyz", "0 0 0")
    rpy = origin.attrib.get("rpy", "0 0 0")
    return f"{xyz} {rpy}"


def model_sdf_path(outdir: str | Path) -> Path:
    """Default per-run path for the converted JX_FLY model SDF."""
    return Path(outdir) / "_artifacts" / "jx_fly_model.sdf"


def urdf_artifact_path(outdir: str | Path) -> Path:
    """Default per-run path for the URDF artifact (for manifest hashing)."""
    return Path(outdir) / "_artifacts" / "jx_fly.urdf"


__all__ = [
    "URDFConversionError",
    "convert_urdf_to_sdf",
    "default_urdf_path",
    "model_sdf_path",
    "urdf_artifact_path",
]