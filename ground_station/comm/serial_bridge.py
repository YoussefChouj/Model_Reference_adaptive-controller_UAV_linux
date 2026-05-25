from __future__ import annotations

import json
import argparse
import queue
import socket
import struct
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import serial  # type: ignore
except ImportError:  # pragma: no cover
    serial = None


# Thread-safe command queue: push dicts to send commands to STM32.
# Expected dict shape:
#   {"cmd_id": int, "index": int, "value": float}
#
# Firmware CMD IDs (TASK/send_data.c Process_GroundStation_Command).
# _pack_command_frame always sends: [0xCC][0xDD][cmd_id][index][float32 LE][CRC8] — no special packing per ID.
#
#   0x01 PID gains   0x02 MRAC gamma   0x03 mixer / u_max
#   0x04 flight mode (idx 0=DangerousStop+abort paths, 1=SDK)
#   0x05 MRAC What_limit   0x06 virtual RC sticks -> virtual_rc_sticks[] (SBUS lost + SDK only)
#   0x07 bench mode (idx 0, val>=0.5 on)   0x08 MRAC What_tol
#   0x09 GS safety: idx 0=max_horiz_m/s 1=max_vert_m/s 2=max_pitch_deg 3=max_roll_deg
#
#   0x0A TWC (point target) — FlyMode_SDK only:
#        idx 0=target_x  1=target_y  2=target_z  3=yaw_deg  4=execute (1=start, 0=stop)
#   0x0B sinusoid path — FlyMode_SDK only:
#        idx 0=center_x 1=center_y 2=center_z 3=amplitude_m 4=freq_Hz 5=duration_s
#            6=axis (0=X 1=Y 2=Z)  7=active (1=start path, 0=disable)
#   0x0C circle path — FlyMode_SDK only:
#        idx 0=center_x 1=center_y 2=center_z 3=radius_m 4=omega_rad_s 5=duration_s  6=active (1=start)
#   0x0D abort all paths (GroundStation_AbortAllPaths) — idx 0 (value ignored; use 1.0)
#   0x0E arm/disarm — idx 0: val>=0.5 = arm (GS_KeySDKflag=1, ARM_REQUEST, RCInput authority on),
#                              val<0.5  = disarm (GS_KeySDKflag=0, DISARM_REQUEST, authority off)
#   0x0F MRAC flags — idx: 0=adaptation_on 1=projection_on 2=deadzone_on 3=hard_freeze_on
#                          4=tanh_saturation_on 5=e_modification_on 6=l1_filtering_on
#                          7=axis_enable_pitch 8=axis_enable_roll 9=axis_enable_yaw
#                          val>=0.5 = ON, val<0.5 = OFF
# Must match GS_PROTO_VERSION in Global_file/global_declare.h.
# Increment both when the telemetry frame layout or CMD semantics change.
GS_PROTO_VERSION: int = 2

cmd_queue: "queue.Queue[Optional[Dict[str, Any]]]" = queue.Queue()


def _parse_simple_yaml(path: Path) -> Dict[str, Any]:
    """
    Minimal YAML parser for simple "key: value" files (no nesting).
    This avoids adding a PyYAML dependency just for config loading.
    """
    result: Dict[str, Any] = {}
    if not path.exists():
        return result

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        # Cast a couple of expected numeric fields.
        if key in {
            "baud_rate",
            "vofa_port",
            "vofa_port_a",
            "vofa_port_b",
            "simulate_udp_port",
            "cmd_udp_port",
            "telemetry_mirror_port",
        }:
            try:
                result[key] = int(value)
            except ValueError:
                pass
        else:
            result[key] = value
    return result


def load_config() -> Dict[str, Any]:
    defaults: Dict[str, Any] = {
        "serial_port": "COM3",
        "baud_rate": 115200,
        "vofa_host": "127.0.0.1",
        "vofa_port": 1347,
        # VOFA+ JustFloat: fixed channel count per connection (Frame A vs Frame B differ).
        "vofa_port_a": 1347,
        "vofa_port_b": 1348,
        "simulate_udp_port": 50007,
        # Dashboard -> serial_bridge control (must differ from vofa_port_b).
        "cmd_udp_port": 1349,
        # One-way JSON telemetry mirror to dashboard (UDP send to this host:port after each decoded frame).
        "telemetry_mirror_host": "127.0.0.1",
        "telemetry_mirror_port": 1350,
        # Dashboard binds here to receive the mirror (same machine as bridge by default).
        "telemetry_mirror_bind": "127.0.0.1",
        # VOFA+ output mode (see _emit_vofa_output):
        #   FireWater text modes often show names in the Rx log but still map to a single channel (I0) on UDP
        #   in VOFA+ 1.3.x — use JustFloat for real multi-channel plots.
        #   firewater_multiline   — legacy: TWO UDP packets (data block + "\\n")
        #   firewater_single_line — one packet: lines "name: val\\n" + final "\\n" (for logging / other tools)
        #   firewater_header_csv  — "!names\\n" then "v0,v1,...\\n"
        #   justfloat (default)   — LE float32 per channel + tail 00 00 80 7F; VOFA shows I0,I1,... (rename in UI)
        #   Channel order = order of (name, value) tuples in _unpack_frame_a / _unpack_frame_b.
        "vofa_format": "justfloat",
    }

    config_path = Path(__file__).resolve().parents[1] / "config.yaml"
    overrides = _parse_simple_yaml(config_path)
    defaults.update(overrides)
    # Legacy: if config only has vofa_port, mirror it to vofa_port_a when vofa_port_a omitted.
    if "vofa_port_a" not in overrides and "vofa_port" in defaults:
        try:
            defaults["vofa_port_a"] = int(defaults["vofa_port"])
        except (TypeError, ValueError):
            pass
    return defaults


def _xor_crc8(data: Iterable[int]) -> int:
    """
    CRC8 in this project is an XOR checksum over bytes.
    Matches the C code:
      crc = 0;
      for (i = 2; i < len; i++) { crc ^= Buf[i]; }
    """
    crc = 0
    for b in data:
        crc ^= (b & 0xFF)
    return crc & 0xFF


def vofa_channel_name(internal_name: str) -> str:
    """FireWater / CSV channel names: dots -> underscores (mrac.pitch.e -> mrac_pitch_e)."""
    return internal_name.replace(".", "_")


class SerialBridge:
    SYNC_0 = 0xAA
    SYNC_1 = 0xBB
    CMD_0 = 0xCC
    CMD_1 = 0xDD

    def __init__(
        self,
        serial_port: Optional[str] = None,
        baud_rate: Optional[int] = None,
        vofa_host: Optional[str] = None,
        vofa_port: Optional[int] = None,
        vofa_port_a: Optional[int] = None,
        vofa_port_b: Optional[int] = None,
        *,
        serial_read_timeout_s: float = 0.2,
        simulate: bool = False,
        simulate_udp_port: Optional[int] = None,
        simulate_bind_host: str = "127.0.0.1",
        cmd_udp_port: Optional[int] = None,
        cmd_bind_host: str = "127.0.0.1",
    ) -> None:
        cfg = load_config()
        self.serial_port = serial_port if serial_port is not None else cfg["serial_port"]
        self.baud_rate = baud_rate if baud_rate is not None else int(cfg["baud_rate"])
        self.vofa_host = vofa_host if vofa_host is not None else cfg["vofa_host"]
        if vofa_port_a is not None:
            self.vofa_port_a = int(vofa_port_a)
        elif vofa_port is not None:
            self.vofa_port_a = int(vofa_port)
        else:
            self.vofa_port_a = int(cfg.get("vofa_port_a", cfg.get("vofa_port", 1347)))
        self.vofa_port_b = (
            int(vofa_port_b) if vofa_port_b is not None else int(cfg.get("vofa_port_b", 1348))
        )
        self.vofa_port = self.vofa_port_a  # legacy alias (Frame A port)
        self._simulate = bool(simulate)
        self._simulate_udp_port = (
            int(simulate_udp_port)
            if simulate_udp_port is not None
            else int(cfg.get("simulate_udp_port", 50007))
        )
        self._simulate_bind_host = simulate_bind_host

        self._cmd_udp_port = (
            int(cmd_udp_port) if cmd_udp_port is not None else int(cfg.get("cmd_udp_port", 1349))
        )
        self._cmd_bind_host = cmd_bind_host

        self._telemetry_mirror_host = str(cfg.get("telemetry_mirror_host", "127.0.0.1"))
        self._telemetry_mirror_port = int(cfg.get("telemetry_mirror_port", 1350))
        self._mirror_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.serial_read_timeout_s = float(serial_read_timeout_s)

        self._stop_event = threading.Event()
        self._rx_thread: Optional[threading.Thread] = None
        self._cmd_thread: Optional[threading.Thread] = None
        self._cmd_udp_thread: Optional[threading.Thread] = None

        self._serial: Any = None
        self._simulate_sock: Optional[socket.socket] = None
        self._cmd_udp_sock: Optional[socket.socket] = None
        self._write_lock = threading.Lock()

        self._udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Thread-safe "latest known values" for the GUI.
        self._state_lock = threading.Lock()
        self._last_max_num_basis: int = 8
        self._last_arm: Optional[float] = None
        self._last_flymode: Optional[float] = None
        self._last_sbus_lost: Optional[float] = None
        self._last_rc_authority: Optional[float] = None
        self._last_telemetry_a: Dict[str, float] = {}
        self._last_telemetry_b: Dict[str, float] = {}
        self._telemetry_lock = threading.Lock()

        # Debug printing throttle (simulate mode can be very chatty).
        self._last_telemetry_print_t = 0.0
        self._telemetry_print_interval_s = 1.0

        self._vofa_format = str(cfg.get("vofa_format", "justfloat")).strip().lower()
        self._vofa_header_sent_a = False
        self._vofa_header_sent_b = False

    def get_last_max_num_basis(self) -> int:
        with self._state_lock:
            return int(self._last_max_num_basis)

    def get_last_arm_status(self) -> Optional[float]:
        with self._state_lock:
            return self._last_arm

    def get_last_flymode(self) -> Optional[float]:
        with self._state_lock:
            return self._last_flymode

    def get_last_sbus_lost(self) -> Optional[float]:
        with self._state_lock:
            return self._last_sbus_lost

    def get_telemetry_snapshot(self) -> Tuple[Dict[str, float], Dict[str, float]]:
        """Latest decoded Frame A / Frame B variables (thread-safe, for GUI + logging)."""
        with self._telemetry_lock:
            return (dict(self._last_telemetry_a), dict(self._last_telemetry_b))

    def start(self) -> None:
        if self._rx_thread and self._rx_thread.is_alive():
            return
        if not self._simulate and serial is None:  # pragma: no cover
            raise ImportError(
                "pyserial is required for SerialBridge (unless --simulate). Install with: pip install pyserial"
            )

        self._stop_event.clear()

        if self._simulate:
            self._serial = None
            self._simulate_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._simulate_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._simulate_sock.bind((self._simulate_bind_host, self._simulate_udp_port))
            self._simulate_sock.settimeout(0.2)
            rx_target = self._rx_loop_udp
        else:
            self._simulate_sock = None
            self._serial = serial.Serial(  # type: ignore[attr-defined]
                port=self.serial_port,
                baudrate=self.baud_rate,
                timeout=self.serial_read_timeout_s,
            )
            rx_target = self._rx_loop

        self._rx_thread = threading.Thread(target=rx_target, name="serial_bridge_rx", daemon=True)
        self._cmd_thread = threading.Thread(
            target=self._cmd_loop, name="serial_bridge_cmd", daemon=True
        )

        # Localhost UDP control channel for the dashboard (JSON commands).
        self._cmd_udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._cmd_udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._cmd_udp_sock.bind((self._cmd_bind_host, self._cmd_udp_port))
        self._cmd_udp_sock.settimeout(0.2)
        self._cmd_udp_thread = threading.Thread(
            target=self._cmd_udp_loop, name="serial_bridge_cmd_udp", daemon=True
        )

        self._rx_thread.start()
        self._cmd_thread.start()
        self._cmd_udp_thread.start()

    def stop(self) -> None:
        self._stop_event.set()

        # Let threads exit their loops quickly.
        try:
            if self._simulate_sock is not None:
                try:
                    self._simulate_sock.close()
                except Exception:
                    pass
                self._simulate_sock = None
            if self._serial is not None:
                try:
                    self._serial.cancel_read()  # type: ignore[attr-defined]
                except Exception:
                    pass
            if self._cmd_udp_sock is not None:
                try:
                    self._cmd_udp_sock.close()
                except Exception:
                    pass
                self._cmd_udp_sock = None
            if getattr(self, "_mirror_sock", None) is not None:
                try:
                    self._mirror_sock.close()
                except Exception:
                    pass
                self._mirror_sock = None
        finally:
            try:
                if self._serial is not None:
                    self._serial.close()
            except Exception:
                pass

        # Best-effort join (threads are daemon; don't block indefinitely).
        for t in (self._rx_thread, self._cmd_thread, self._cmd_udp_thread):
            if t is not None and t.is_alive():
                t.join(timeout=1.0)

    def _read_exact(self, n: int) -> Optional[bytes]:
        if self._serial is None:
            return None
        buf = bytearray()
        while len(buf) < n and not self._stop_event.is_set():
            chunk = self._serial.read(n - len(buf))
            if not chunk:
                continue
            buf.extend(chunk)
        if len(buf) != n:
            return None
        return bytes(buf)

    def _emit_vofa_output(self, frame_type: int, lines: List[Tuple[str, float]]) -> None:
        """Send one telemetry burst to VOFA+ according to config `vofa_format` and frame type."""
        dest_port = self.vofa_port_a if frame_type == 0x01 else self.vofa_port_b
        fmt = self._vofa_format
        if fmt == "justfloat":
            self._emit_justfloat(lines, dest_port)
        elif fmt == "firewater_single_line":
            self._emit_firewater_single_line(lines, dest_port)
        elif fmt == "firewater_header_csv":
            self._emit_firewater_header_csv(lines, frame_type, dest_port)
        elif fmt == "firewater_multiline":
            self._emit_firewater_multiline(lines, dest_port)
        else:
            self._emit_firewater_single_line(lines, dest_port)

    def _emit_firewater_multiline(self, lines: List[Tuple[str, float]], dest_port: int) -> None:
        # One "name: val\\n" per variable, then a blank line (second UDP) to advance time axis.
        dat = "".join(
            f"{vofa_channel_name(name)}: {val:.6f}\n" for name, val in lines
        ).encode("utf-8")
        dest = (self.vofa_host, dest_port)
        self._udp_sock.sendto(dat, dest)
        self._udp_sock.sendto(b"\n", dest)

    def _emit_firewater_single_line(self, lines: List[Tuple[str, float]], dest_port: int) -> None:
        # FireWater: one line per channel, entire burst in a SINGLE UDP datagram (VOFA+ 1.3.x).
        payload = ""
        for name, val in lines:
            payload += f"{vofa_channel_name(name)}: {val:.6f}\n"
        payload += "\n"  # time advance
        self._udp_sock.sendto(payload.encode("utf-8"), (self.vofa_host, dest_port))

    def _emit_firewater_header_csv(
        self, lines: List[Tuple[str, float]], frame_type: int, dest_port: int
    ) -> None:
        # Attempt 3: declare names once per port/stream, then values-only rows.
        dest = (self.vofa_host, dest_port)
        names = [vofa_channel_name(n) for n, _ in lines]
        header_ok = self._vofa_header_sent_a if frame_type == 0x01 else self._vofa_header_sent_b
        if not header_ok:
            hdr = "!" + ",".join(names) + "\n"
            self._udp_sock.sendto(hdr.encode("utf-8"), dest)
            if frame_type == 0x01:
                self._vofa_header_sent_a = True
            else:
                self._vofa_header_sent_b = True
        body = ",".join(f"{val:.6f}" for _, val in lines) + "\n"
        self._udp_sock.sendto(body.encode("utf-8"), dest)

    def _emit_justfloat(self, lines: List[Tuple[str, float]], dest_port: int) -> None:
        """VOFA+ JustFloat: little-endian float32 payload + frame tail bytes."""
        vals = [float(v) for _, v in lines]
        n = len(vals)
        payload = struct.pack("<" + "f" * n, *vals) + b"\x00\x00\x80\x7f"
        self._udp_sock.sendto(payload, (self.vofa_host, dest_port))

    def _unpack_frame_a(self, max_num_basis: int, payload: bytes) -> List[Tuple[str, float]]:
        # JUSTFLOAT CHANNEL MAP - Frame A (100Hz) -> VOFA UDP vofa_port_a (default 1347)
        # I0  = mrac_pitch_e
        # I1  = mrac_pitch_u_ad
        # I2  = mrac_roll_e
        # I3  = mrac_roll_u_ad
        # I4  = mrac_yaw_e
        # I5  = mrac_yaw_u_ad
        # I6  = mrac_z_e
        # I7  = mrac_z_u_ad
        # I8  = status_arm
        # I9  = status_flymode
        # I10 = status_sbus_lost
        # I11 = status_twc_execute
        # I12 = status_twc_arrived
        #
        # Payload layout (LEN=38):
        #   float pitch.e
        #   float pitch.u_ad
        #   float roll.e
        #   float roll.u_ad
        #   float yaw.e
        #   float yaw.u_ad
        #   float z.e          (uses mrac_state.z_rate.e)
        #   float z.u_ad       (uses mrac_state.z_rate.u_ad)
        #   uint8 status.arm
        #   uint8 status.flymode
        #   uint8 status.sbus_lost
        #   uint8 status.twc_execute
        #   uint8 status.twc_arrived
        #   uint8 rc_authority   <- 1=PC authority, 0=RC (added in v2)
        #   uint8 proto_version  <- GS_PROTO_VERSION
        if len(payload) != 39:
            return []
        fmt = "<8fBBBBBBB"
        (
            p_e,
            p_u,
            r_e,
            r_u,
            y_e,
            y_u,
            z_e,
            z_u,
            arm_u8,
            flymode_u8,
            sbus_lost_u8,
            twc_exec_u8,
            twc_arr_u8,
            rc_authority_u8,
            proto_ver_u8,
        ) = struct.unpack(fmt, payload)
        if proto_ver_u8 != GS_PROTO_VERSION:
            print(
                f"WARNING: firmware proto_version={proto_ver_u8} != expected {GS_PROTO_VERSION}. "
                "Reflash firmware or update serial_bridge.py.",
                flush=True,
            )

        # Update GUI state for ARM / flymode and MRAC basis hiding.
        with self._state_lock:
            self._last_max_num_basis = int(max_num_basis)
            self._last_arm = float(arm_u8)
            self._last_flymode = float(flymode_u8)
            self._last_sbus_lost = float(sbus_lost_u8)
            self._last_rc_authority = float(rc_authority_u8)

        return [
            ("mrac.pitch.e", float(p_e)),
            ("mrac.pitch.u_ad", float(p_u)),
            ("mrac.roll.e", float(r_e)),
            ("mrac.roll.u_ad", float(r_u)),
            ("mrac.yaw.e", float(y_e)),
            ("mrac.yaw.u_ad", float(y_u)),
            ("mrac.z.e", float(z_e)),
            ("mrac.z.u_ad", float(z_u)),
            ("status.arm", float(arm_u8)),
            ("status.flymode", float(flymode_u8)),
            ("status.sbus_lost", float(sbus_lost_u8)),
            ("status.twc_execute", float(twc_exec_u8)),
            ("status.twc_arrived", float(twc_arr_u8)),
            ("status.rc_authority", float(rc_authority_u8)),
        ]

    def _unpack_frame_b(self, max_num_basis: int, payload: bytes) -> List[Tuple[str, float]]:
        # JUSTFLOAT CHANNEL MAP - Frame B (20Hz) -> VOFA UDP vofa_port_b (default 1348)
        # Map below is for MAX_NUM_BASIS=6 (59 channels). Total count = 4*(MAX_NUM_BASIS+2)+27; theta_* spans 0..MAX_NUM_BASIS-1 per axis.
        # I0  = mrac_pitch_theta_0
        # I1  = mrac_pitch_theta_1
        # I2  = mrac_pitch_theta_2
        # I3  = mrac_pitch_theta_3
        # I4  = mrac_pitch_theta_4
        # I5  = mrac_pitch_theta_5
        # I6  = mrac_pitch_u_nom
        # I7  = mrac_pitch_xm
        # I8  = mrac_roll_theta_0
        # I9  = mrac_roll_theta_1
        # I10 = mrac_roll_theta_2
        # I11 = mrac_roll_theta_3
        # I12 = mrac_roll_theta_4
        # I13 = mrac_roll_theta_5
        # I14 = mrac_roll_u_nom
        # I15 = mrac_roll_xm
        # I16 = mrac_yaw_theta_0
        # I17 = mrac_yaw_theta_1
        # I18 = mrac_yaw_theta_2
        # I19 = mrac_yaw_theta_3
        # I20 = mrac_yaw_theta_4
        # I21 = mrac_yaw_theta_5
        # I22 = mrac_yaw_u_nom
        # I23 = mrac_yaw_xm
        # I24 = mrac_z_theta_0
        # I25 = mrac_z_theta_1
        # I26 = mrac_z_theta_2
        # I27 = mrac_z_theta_3
        # I28 = mrac_z_theta_4
        # I29 = mrac_z_theta_5
        # I30 = mrac_z_u_nom
        # I31 = mrac_z_xm
        # I32 = pid_pitch_FB
        # I33 = pid_pitch_Des
        # I34 = pid_pitch_U
        # I35 = pid_roll_FB
        # I36 = pid_roll_Des
        # I37 = pid_roll_U
        # I38 = pid_yaw_FB
        # I39 = pid_yaw_Des
        # I40 = pid_yaw_U
        # I41 = pid_gyrox_FB
        # I42 = pid_gyrox_Des
        # I43 = pid_gyrox_U
        # I44 = pid_gyroy_FB
        # I45 = pid_gyroy_Des
        # I46 = pid_gyroy_U
        # I47 = pid_gyroz_FB
        # I48 = pid_gyroz_Des
        # I49 = pid_gyroz_U
        # I50 = pid_z_rate_FB
        # I51 = pid_z_rate_Des
        # I52 = pid_z_rate_U
        # I53 = pid_locx_FB
        # I54 = pid_locx_Des
        # I55 = pid_locx_U
        # I56 = pid_locy_FB
        # I57 = pid_locy_Des
        # I58 = pid_locy_U
        # I59..I67 = pid_z_pos (FB,Des,U), pid_locxs (FB,Des,U), pid_locys (FB,Des,U)
        #
        # Payload layout is floats only.
        # MRAC axes: pitch, roll, yaw, z_rate (mapped to axis name 'z')
        #   theta[0..MAX_NUM_BASIS-1], u_nom, xm  => (MAX_NUM_BASIS + 2) floats per axis
        # PID loops (12): + z_pos, locxs, locys (optical flow velocity + altitude)
        #   FB, Des, U => 3 floats per loop
        total_floats = 4 * (max_num_basis + 2) + 36
        main_len = total_floats * 4
        path_tail_len = 22  # u8 + 3f + f + f + u8 (path state, see send_data.c Frame B)
        if len(payload) != main_len + path_tail_len:
            return []

        fmt = "<" + ("f" * total_floats)
        vals = struct.unpack(fmt, payload[:main_len])
        tail = payload[main_len : main_len + path_tail_len]
        (apm_u8, twc_tx, twc_ty, twc_tz, sin_te, circ_th, twc_arr_u8) = struct.unpack("<BfffffB", tail)

        # Update GUI state for MRAC basis hiding.
        with self._state_lock:
            self._last_max_num_basis = int(max_num_basis)

        out: List[Tuple[str, float]] = []
        idx = 0

        axes = ["pitch", "roll", "yaw", "z"]
        for axis in axes:
            for b in range(max_num_basis):
                out.append((f"mrac.{axis}.theta_{b}", float(vals[idx])))
                idx += 1
            out.append((f"mrac.{axis}.u_nom", float(vals[idx])))
            idx += 1
            out.append((f"mrac.{axis}.xm", float(vals[idx])))
            idx += 1

        pid_loops = [
            "pitch",
            "roll",
            "yaw",
            "gyrox",
            "gyroy",
            "gyroz",
            "z_rate",
            "locx",
            "locy",
            "z_pos",
            "locxs",
            "locys",
        ]
        for loop in pid_loops:
            out.append((f"pid.{loop}.FB", float(vals[idx])))
            idx += 1
            out.append((f"pid.{loop}.Des", float(vals[idx])))
            idx += 1
            out.append((f"pid.{loop}.U", float(vals[idx])))
            idx += 1

        out.append(("path.active_path_mode", float(apm_u8)))
        out.append(("path.twc_target_x", float(twc_tx)))
        out.append(("path.twc_target_y", float(twc_ty)))
        out.append(("path.twc_target_z", float(twc_tz)))
        out.append(("path.sinusoid_t_elapsed", float(sin_te)))
        out.append(("path.circle_theta", float(circ_th)))
        out.append(("path.twc_arrived", float(twc_arr_u8)))

        return out

    def _handle_frame(self, frame_type: int, max_num_basis: int, payload: bytes) -> None:
        if frame_type == 0x01:
            lines = self._unpack_frame_a(max_num_basis, payload)
        elif frame_type == 0x02:
            lines = self._unpack_frame_b(max_num_basis, payload)
        else:
            return

        if lines:
            mp: Dict[str, float] = {k: float(v) for k, v in lines}
            with self._telemetry_lock:
                if frame_type == 0x01:
                    self._last_telemetry_a = mp
                else:
                    self._last_telemetry_b = mp
            self._maybe_debug_print_telemetry(frame_type, lines)
            self._emit_vofa_output(frame_type, lines)
            self._mirror_telemetry_udp()

    def _mirror_telemetry_udp(self) -> None:
        """Push latest Frame A/B dicts + max_num_basis to dashboard via UDP (JSON, one-way)."""
        try:
            with self._telemetry_lock:
                a = dict(self._last_telemetry_a)
                b = dict(self._last_telemetry_b)
            with self._state_lock:
                mb = int(self._last_max_num_basis)
            payload = json.dumps(
                {"a": a, "b": b, "max_num_basis": mb},
                separators=(",", ":"),
            ).encode("utf-8")
            if len(payload) > 65000:
                return
            self._mirror_sock.sendto(payload, (self._telemetry_mirror_host, self._telemetry_mirror_port))
        except Exception:
            pass

    def _maybe_debug_print_telemetry(self, frame_type: int, lines: List[Tuple[str, float]]) -> None:
        if not self._simulate:
            return
        now = time.monotonic()
        if now - self._last_telemetry_print_t < self._telemetry_print_interval_s:
            return
        self._last_telemetry_print_t = now

        sample = lines[:6]
        sample_str = ", ".join([f"{name}={val:.4g}" for name, val in sample])
        print(
            f"Decoded telemetry frame=0x{frame_type:02X} vars({len(lines)}) sample: {sample_str}",
            flush=True,
        )

    def _format_frame_bytes(self, frame: bytes) -> str:
        return "".join([f"[0x{b:02X}]" for b in frame])

    def _print_tx_frame(self, frame: bytes, cmd: Dict[str, Any]) -> None:
        # Frame layout:
        #   [0xCC][0xDD][CMD_ID][INDEX][VALUE float32 LE][CRC8]
        try:
            cmd_id = frame[2]
            index = frame[3]
            value_f = struct.unpack("<f", frame[4:8])[0]
        except Exception:
            cmd_id = int(cmd.get("cmd_id", 0)) & 0xFF
            index = int(cmd.get("index", 0)) & 0xFF
            value_f = float(cmd.get("value", 0.0))
        print(
            f"TX cmd_frame={self._format_frame_bytes(frame)} cmd_id=0x{cmd_id:02X} index={index} value={value_f:.6g}",
            flush=True,
        )

    def _cmd_udp_loop(self) -> None:
        """
        Dashboard control channel (localhost):
          - send literal `b"ping"` to receive `b"pong"`
          - send JSON: {"cmd_id": int, "index": int, "value": float}
        """
        if self._cmd_udp_sock is None:
            return

        while not self._stop_event.is_set():
            try:
                data, addr = self._cmd_udp_sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break

            if data == b"ping":
                try:
                    self._cmd_udp_sock.sendto(b"pong", addr)
                except Exception:
                    pass
                continue

            try:
                msg = json.loads(data.decode("utf-8"))
            except Exception:
                continue
            if not isinstance(msg, dict):
                continue

            # Normalize a few alternate keys.
            if "cmd_id" not in msg:
                if "CMD_ID" in msg:
                    msg["cmd_id"] = msg["CMD_ID"]
            if "index" not in msg:
                for k in ("idx", "INDEX"):
                    if k in msg:
                        msg["index"] = msg[k]
                        break
            if "value" not in msg:
                for k in ("val", "VALUE"):
                    if k in msg:
                        msg["value"] = msg[k]
                        break

            try:
                cmd_queue.put(msg)
            except Exception:
                continue

    def _parse_and_handle_datagram(self, data: bytes) -> None:
        """
                Parse one complete telemetry datagram from the UDP simulation path.

                Byte layout:
                    [0xAA][0xBB][frame_type][LEN_high][LEN_low][MAX_NUM_BASIS][payload][CRC8]

                Validation order:
                    1) Minimum frame size (7 bytes).
                    2) Sync bytes match self.SYNC_0/self.SYNC_1.
                    3) Frame-type specific payload length is valid.
                    4) Payload length bounds are within (0, 4096].
                    5) Full datagram size matches header + payload + CRC.
                    6) XOR CRC8 over [frame_type, LEN_high, LEN_low, MAX_NUM_BASIS, payload]
                         equals trailing CRC byte.

                If all checks pass, payload is forwarded to
                self._handle_frame(frame_type, max_num_basis, payload).
        """
        if len(data) < 7:
            return
        if data[0] != self.SYNC_0 or data[1] != self.SYNC_1:
            return
        frame_type = data[2]
        len_high = data[3]
        len_low = data[4]
        len_payload = (len_high << 8) | len_low
        max_num_basis = data[5]

        if frame_type == 0x01:
            if len_payload != 39:
                return
        elif frame_type == 0x02:
            total_floats = 4 * (max_num_basis + 2) + 36
            expected_len = total_floats * 4 + 22
            if len_payload != expected_len:
                return
        else:
            return

        if len_payload <= 0 or len_payload > 4096:
            return

        expected_total = 6 + len_payload + 1
        if len(data) != expected_total:
            return

        payload = data[6 : 6 + len_payload]
        recv_crc = data[6 + len_payload]
        calc_crc = _xor_crc8([frame_type, len_high, len_low, max_num_basis, *payload])
        if calc_crc != recv_crc:
            return

        self._handle_frame(frame_type, max_num_basis, payload)

    def _rx_loop_udp(self) -> None:
        """Receive full frames from frame_simulator (UDP) instead of UART."""
        if self._simulate_sock is None:
            return
        while not self._stop_event.is_set():
            try:
                data, _addr = self._simulate_sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            self._parse_and_handle_datagram(data)

    def _rx_loop(self) -> None:
        """
        RX loop:
          - sync on [0xAA][0xBB]
          - read frame_type, LEN_high, LEN_low, MAX_NUM_BASIS
          - read payload ((LEN_high<<8)|LEN_low bytes)
          - read CRC8 (1 byte)
          - validate XOR checksum, drop corrupt frames silently
          - forward decoded variables via FireWater over UDP
        """
        if self._serial is None:
            return

        sync_seen = False
        while not self._stop_event.is_set():
            b = self._serial.read(1)
            if not b:
                continue
            byte = b[0]

            if not sync_seen:
                if byte == self.SYNC_0:
                    sync_seen = True
                continue

            # sync_seen means we already saw 0xAA.
            if byte != self.SYNC_1:
                sync_seen = byte == self.SYNC_0
                continue

            header = self._read_exact(4)
            if header is None:
                break

            frame_type = header[0]
            len_high = header[1]
            len_low = header[2]
            max_num_basis = header[3]
            len_payload = (len_high << 8) | len_low

            # Basic header sanity checks to avoid blocking on corrupted LEN values.
            if frame_type == 0x01:
                if len_payload != 39:
                    sync_seen = False
                    continue
            elif frame_type == 0x02:
                total_floats = 4 * (max_num_basis + 2) + 36
                expected_len = total_floats * 4 + 22
                if len_payload != expected_len:
                    sync_seen = False
                    continue
            else:
                sync_seen = False
                continue

            if len_payload <= 0 or len_payload > 4096:
                sync_seen = False
                continue

            payload = self._read_exact(len_payload)
            if payload is None:
                break

            crc_b = self._read_exact(1)
            if crc_b is None:
                break
            recv_crc = crc_b[0]

            # CRC is XOR over bytes after sync: type, LEN_hi, LEN_lo, MAX_NUM_BASIS, payload
            calc_crc = _xor_crc8([frame_type, len_high, len_low, max_num_basis, *payload])
            if calc_crc != recv_crc:
                # Drop corrupt frames silently.
                sync_seen = False
                continue

            self._handle_frame(frame_type, max_num_basis, payload)
            sync_seen = False

    def _cmd_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                cmd = cmd_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if self._stop_event.is_set():
                return
            if not isinstance(cmd, dict):
                continue

            try:
                frame = self._pack_command_frame(cmd)
            except Exception:
                # Never let malformed commands kill the background process.
                continue

            try:
                if self._serial is None:
                    if self._simulate:
                        self._print_tx_frame(frame, cmd)
                    continue
                with self._write_lock:
                    self._serial.write(frame)
            except Exception:
                # Best-effort: if serial is gone, exit loop.
                continue

    def _pack_command_frame(self, cmd: Dict[str, Any]) -> bytes:
        # Accept a few key aliases to be forgiving.
        cmd_id = cmd.get("cmd_id", cmd.get("id", cmd.get("CMD_ID")))
        index = cmd.get("index", cmd.get("idx", cmd.get("INDEX")))
        value = cmd.get("value", cmd.get("val", cmd.get("VALUE")))

        if cmd_id is None or index is None or value is None:
            raise ValueError("cmd dict must include cmd_id/index/value")

        cmd_id_u8 = int(cmd_id) & 0xFF
        index_u8 = int(index) & 0xFF
        value_f = float(value)

        value_bytes = struct.pack("<f", value_f)

        # [0xCC] [0xDD] [CMD_ID] [INDEX] [VALUE float32 LE] [CRC8]
        header_and_payload = bytes([self.CMD_0, self.CMD_1, cmd_id_u8, index_u8]) + value_bytes
        # CRC in C is XOR over bytes 2..7 (cmd_id, index, and 4 bytes of value).
        crc = _xor_crc8(header_and_payload[2:])
        return header_and_payload + bytes([crc])


def test_com_ports_listen(
    ports: Optional[List[str]] = None,
    baud_rate: Optional[int] = None,
    wait_s: float = 3.0,
) -> Dict[str, int]:
    """
    Open each serial port briefly, wait for incoming bytes, report counts.
    Used to find which COM port is the wireless UART debugger / vehicle link.
    """
    cfg = load_config()
    br = int(cfg.get("baud_rate", 115200)) if baud_rate is None else int(baud_rate)
    try_list = ports if ports is not None else ["COM6", "COM4", "COM5"]
    out: Dict[str, int] = {}
    if serial is None:  # pragma: no cover
        print("pyserial not installed; cannot test COM ports.")
        return out
    for port in try_list:
        n = 0
        try:
            ser = serial.Serial(port=port, baudrate=br, timeout=0.05)  # type: ignore[attr-defined]
            try:
                t_end = time.monotonic() + float(wait_s)
                while time.monotonic() < t_end:
                    chunk = ser.read(4096)
                    if chunk:
                        n += len(chunk)
                print(f"{port}: received {n} bytes")
            finally:
                ser.close()
        except Exception as e:
            print(f"{port}: open/read failed ({e})")
            n = -1
        out[port] = n
    return out


def start_bridge_in_background(
    *,
    simulate: bool = False,
    simulate_udp_port: Optional[int] = None,
) -> SerialBridge:
    """
    Convenience helper for quick manual runs:
      bridge = start_bridge_in_background()
      ...
      bridge.stop()
    """
    bridge = SerialBridge(simulate=simulate, simulate_udp_port=simulate_udp_port)
    bridge.start()
    return bridge


def _main_cli() -> None:
    p = argparse.ArgumentParser(description="UART4 telemetry bridge → VOFA+ FireWater (UDP).")
    p.add_argument(
        "--simulate",
        action="store_true",
        help="Read synthetic frames from UDP (frame_simulator.py) instead of serial.",
    )
    p.add_argument(
        "--simulate-port",
        type=int,
        default=None,
        metavar="PORT",
        help="UDP port to bind for simulate mode (default: config simulate_udp_port or 50007).",
    )
    p.add_argument(
        "--test-com",
        action="store_true",
        help="Try COM6/COM4/COM5 at config baud for 3s each; print byte counts (no bridge).",
    )
    args = p.parse_args()
    if args.test_com:
        test_com_ports_listen()
        return
    port = args.simulate_port
    b = start_bridge_in_background(simulate=args.simulate, simulate_udp_port=port)
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        b.stop()


if __name__ == "__main__":  # pragma: no cover
    _main_cli()

