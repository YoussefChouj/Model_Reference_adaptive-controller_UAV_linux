from __future__ import annotations

import math
import queue
import re
import shutil
import subprocess
import sys, os
import threading
import time
import json
import socket
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# Allow `python ground_station/gui/dashboard.py` from the repo root without PYTHONPATH.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

try:
    import dearpygui.dearpygui as dpg
except ImportError as e:  # pragma: no cover
    raise SystemExit(
        "Dear PyGui is required for the dashboard. Install with: pip install dearpygui"
    ) from e

from ground_station.comm.serial_bridge import SerialBridge, load_config

from ground_station.scripts.flight_logger import FlightLogger


class UdpBridgeClient:
    """Send ground-station commands to a running `serial_bridge.py` process."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = int(port)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.settimeout(0.2)

    def ping(self) -> bool:
        try:
            self._sock.sendto(b"ping", (self.host, self.port))
            data, _addr = self._sock.recvfrom(1024)
            return data == b"pong"
        except Exception:
            return False

    def send_cmd(self, cmd_id: int, index: int, value: float) -> None:
        payload = json.dumps({"cmd_id": int(cmd_id), "index": int(index), "value": float(value)}).encode(
            "utf-8"
        )
        self._sock.sendto(payload, (self.host, self.port))

    def close(self) -> None:
        try:
            self._sock.close()
        except Exception:
            pass


AXES: Dict[str, int] = {
    "pitch": 0,
    "roll": 1,
    "yaw": 2,
    "z": 3,
}

PID_GAIN_IDXS = {
    "Kp": 0,
    "Ki": 1,
    "Kd": 2,
}

# STM32 PID command mapping (PIDTypeDef array in send_data.c Process_GroundStation_Command)
# 0: pitchPID, 1: rollPID, 2: yawPID
# 3: gyroxPID, 4: gyroyPID, 5: gyrozPID
# 6: Z_ratePID (only Z-axis rate loop in firmware — no separate angle loop)
OUTER_PID_AXIS_TO_PIDS = {
    "pitch": 0,
    "roll": 1,
    "yaw": 2,
}
INNER_PID_AXIS_TO_PIDS = {
    "pitch": 3,  # gyroxPID
    "roll": 4,  # gyroyPID
    "yaw": 5,  # gyrozPID
}
Z_RATE_PID_INDEX = 6  # Ctrler.Z_ratePID — sole PID block for Z tab sliders

# Stick PWM units (RemoterTask / StabilizerTask): ~2000–4000, center 3000
RC_THR_MIN = 2000
RC_THR_MAX = 4000
RC_STICK_MIN = 2000
RC_STICK_MAX = 4000
RC_STICK_MID = 3000
# Bench mode: firmware clamps throttle to min + 20% of full range
BENCH_THR_MAX = int(RC_THR_MIN + 0.2 * (RC_THR_MAX - RC_THR_MIN))


def _simple_yaml_kv_load(path: Path) -> Dict[str, Any]:
    """
    Load a config.yaml that is only flat 'key: value' entries.
    This matches how serial_bridge.py reads config.yaml (no nesting).
    """
    if not path.exists():
        return {}
    out: Dict[str, Any] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # Cast obvious numeric fields.
        if re.fullmatch(r"-?\d+", value):
            out[key] = int(value)
        elif re.fullmatch(r"-?\d+\.\d*", value):
            out[key] = float(value)
        else:
            out[key] = value
    return out


def _simple_yaml_kv_write(path: Path, cfg: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Keep deterministic ordering for readability.
    preferred_order = [
        "serial_port",
        "baud_rate",
        "vofa_host",
        "vofa_port",
        "vofa_port_a",
        "vofa_port_b",
        "vofa_executable",
    ]
    keys = list(cfg.keys())
    keys.sort(key=lambda k: preferred_order.index(k) if k in preferred_order else len(preferred_order))
    lines: List[str] = []
    for k in keys:
        v = cfg[k]
        if isinstance(v, str):
            lines.append(f"{k}: {v}")
        else:
            lines.append(f"{k}: {v}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _split_top_level(s: str, sep: str = ",") -> List[str]:
    """Split by sep while respecting [...] bracket nesting."""
    parts: List[str] = []
    buf: List[str] = []
    depth = 0
    for ch in s:
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth = max(0, depth - 1)
        if ch == sep and depth == 0:
            part = "".join(buf).strip()
            if part:
                parts.append(part)
            buf = []
        else:
            buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def _parse_inline_value(raw: str) -> Any:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        items = _split_top_level(inner, ",")
        return [float(x.strip()) for x in items if x.strip()]
    if raw.startswith("{") and raw.endswith("}"):
        return _parse_inline_map(raw)
    # number?
    if re.fullmatch(r"-?\d+(\.\d+)?([eE]-?\d+)?", raw):
        return float(raw) if (("." in raw) or ("e" in raw.lower())) else int(raw)
    return raw.strip('"').strip("'")


def _parse_inline_map(raw: str) -> Dict[str, Any]:
    raw = raw.strip()
    if not (raw.startswith("{") and raw.endswith("}")):
        raise ValueError(f"Expected inline map: {raw}")
    inner = raw[1:-1].strip()
    if not inner:
        return {}
    out: Dict[str, Any] = {}
    for item in _split_top_level(inner, ","):
        if ":" not in item:
            continue
        k, v = item.split(":", 1)
        out[k.strip()] = _parse_inline_value(v)
    return out


def _format_inline_map(d: Dict[str, Any]) -> str:
    # Stable key ordering for consistent presets.
    parts: List[str] = []
    for k in ["Kp", "Ki", "Kd", "gamma", "What_limit", "What_tol", "MRAC_TO_MIXER", "U_MAX"]:
        if k in d:
            v = d[k]
            if isinstance(v, list):
                parts.append(f"{k}: [{', '.join(str(float(x)) for x in v)}]")
            else:
                parts.append(f"{k}: {v}")
    for k, v in d.items():
        if k in {"Kp", "Ki", "Kd", "gamma", "What_limit", "What_tol", "MRAC_TO_MIXER", "U_MAX"}:
            continue
        if isinstance(v, list):
            parts.append(f"{k}: [{', '.join(str(float(x)) for x in v)}]")
        else:
            parts.append(f"{k}: {v}")
    return "{ " + ", ".join(parts) + " }"


def load_preset_yaml(path: Path) -> Dict[str, Any]:
    """
    Minimal loader for the preset format described in the prompt.
    It does NOT implement full YAML; it only supports the exact inline map/list style.
    """
    axis_order = ["pitch", "roll", "yaw", "z"]
    cur_axis: Optional[str] = None
    out: Dict[str, Any] = {}

    # Normalize indentation for predictable parsing.
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        if indent == 0 and stripped.endswith(":") and stripped[:-1] in axis_order:
            cur_axis = stripped[:-1]
            out[cur_axis] = {}
            continue

        if cur_axis is None:
            continue

        # Lines like:   outer_pid: {Kp: 2.0, ...}
        if ":" in stripped and indent >= 2:
            k, v = stripped.split(":", 1)
            k = k.strip()
            v = v.strip()
            if v.startswith("{") and v.endswith("}"):
                out[cur_axis][k] = _parse_inline_map(v)
            elif v.startswith("[") and v.endswith("]"):
                out[cur_axis][k] = _parse_inline_value(v)
            else:
                out[cur_axis][k] = _parse_inline_value(v)

    return out


def dump_preset_yaml(path: Path, payload: Dict[str, Any]) -> None:
    presets: List[str] = []
    for axis in ["pitch", "roll", "yaw", "z"]:
        presets.append(f"{axis}:")
        axis_payload = payload.get(axis, {})

        outer_pid = axis_payload.get("outer_pid", {})
        inner_pid = axis_payload.get("inner_pid", {})
        mrac = axis_payload.get("mrac", {})
        mixer = axis_payload.get("mixer", {})

        if outer_pid:
            presets.append("  outer_pid: " + _format_inline_map(outer_pid))
        if inner_pid:
            presets.append("  inner_pid: " + _format_inline_map(inner_pid))
        if mrac:
            presets.append("  mrac: " + _format_inline_map(mrac))
        if mixer:
            presets.append("  mixer: " + _format_inline_map(mixer))

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(presets) + "\n", encoding="utf-8")


class DebouncedSender:
    def __init__(self, delay_s: float = 0.05) -> None:
        self.delay_s = delay_s
        self._lock = threading.Lock()
        self._timers: Dict[str, threading.Timer] = {}
        self._latest: Dict[str, Tuple[Callable[..., None], Tuple[Any, ...], Dict[str, Any]]] = {}

    def call(self, key: str, fn: Callable[..., None], *args: Any, **kwargs: Any) -> None:
        with self._lock:
            self._latest[key] = (fn, args, kwargs)
            t_prev = self._timers.get(key)
            if t_prev is not None:
                t_prev.cancel()
            t = threading.Timer(self.delay_s, self._flush, args=(key,))
            t.daemon = True
            self._timers[key] = t
            t.start()

    def _flush(self, key: str) -> None:
        with self._lock:
            rec = self._latest.pop(key, None)
            self._timers.pop(key, None)
        if rec is None:
            return
        fn, args, kwargs = rec
        try:
            fn(*args, **kwargs)
        except Exception:
            # Never allow UI changes to crash the GUI loop.
            return


class Dashboard:
    def __init__(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]  # ground_station/
        self.presets_dir = self.repo_root / "presets"
        self.config_path = self.repo_root / "config.yaml"
        self._vofa_runtime_root = self.repo_root / ".vofa_runtime"
        self._vofa_procs: dict[str, Optional[subprocess.Popen]] = {"a": None, "b": None}

        self.bridge: Optional[SerialBridge] = None
        self._udp: Optional[UdpBridgeClient] = None
        self._remote_bridge = False
        self._cmd_host = "127.0.0.1"
        self._cmd_port = int(load_config().get("cmd_udp_port", 1349))
        self.connected = False
        self._loading_preset = False

        self._debouncer = DebouncedSender(delay_s=0.05)

        self._vofa_executable: Optional[str] = None
        self._vofa_checked = False
        self._last_connect_error: str = ""

        # Slider tags for preset save/load.
        self.outer_pid: Dict[str, Dict[str, Any]] = {}
        self.inner_pid: Dict[str, Dict[str, Any]] = {}
        self.mrac_gamma: Dict[str, List[Any]] = {}
        self.mrac_what_limit: Dict[str, List[Any]] = {}
        self.mrac_what_tol: Dict[str, List[Any]] = {}
        self.mixer_slider: Dict[str, Any] = {}
        self.u_max_slider: Dict[str, Any] = {}

        self.arm_label_tag: Any = None
        self.arm_value_tag: Any = None

        self.max_num_basis: int = 8
        self.mrac_slider_tags: List[Tuple[str, str, int, Any]] = []  # axis, kind, i, tag

        self.vrc_slider_tags: List[Any] = []
        self._bench_mode_ui: bool = False

        self._flight_logger = FlightLogger()
        self._path_abort_flag: List[bool] = [False]
        self._position_source: str = "None"
        self._expert_mode: bool = False
        self._recording_flight: bool = False
        self._recording_path: bool = False
        self._path_point_buffer: List[Tuple[float, float]] = []
        self._last_log_t: float = 0.0
        self._last_path_sample_t: float = 0.0
        self._current_preset_label: str = "(none)"
        self._mon_mrac_tags: Dict[str, Any] = {}
        self._mon_pid_text_tags: Dict[str, Any] = {}

        self._last_paths_canvas_t: float = 0.0
        self._path_exec_trace: List[Tuple[float, float]] = []
        self._last_telem_rx_t: float = 0.0

        # Unified telemetry: UDP mirror (remote bridge) + direct copy when local SerialBridge in-process.
        self._telem: Dict[str, Any] = {"a": {}, "b": {}, "max_num_basis": 8}
        self._telem_stop = threading.Event()
        self._telem_thread = threading.Thread(target=self._telemetry_listener, name="dashboard_telemetry_udp", daemon=True)
        self._telem_thread.start()
        self._ui_actions: queue.SimpleQueue[Tuple[Callable[..., Any], Tuple[Any, ...], Dict[str, Any]]] = queue.SimpleQueue()

        self._build_gui()
        self._refresh_preset_list()

        # Start the bridge immediately (per prompt).
        self._connect_on_launch()
        # Path buttons depend on position source even before first render tick.
        try:
            self._paths_refresh_ui()
        except Exception:
            pass

        # Poll bridge state for ARM + MAX_NUM_BASIS updates (throttled inside _frame).
        self._last_poll_t = 0.0

    def _telemetry_listener(self) -> None:
        cfg = load_config()
        port = int(cfg.get("telemetry_mirror_port", 1350))
        host = str(cfg.get("telemetry_mirror_bind", "127.0.0.1"))
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
        except Exception as ex:
            print(
                f"dashboard: telemetry mirror bind {host}:{port} failed ({ex!r}); "
                "remote-bridge telemetry via UDP unavailable (local SerialBridge still works).",
                flush=True,
            )
            try:
                sock.close()
            except Exception:
                pass
            return
        sock.settimeout(0.25)
        while not self._telem_stop.is_set():
            try:
                data, _addr = sock.recvfrom(65535)
                msg = json.loads(data.decode("utf-8"))
                if not isinstance(msg, dict):
                    continue
                if "a" in msg and isinstance(msg["a"], dict):
                    self._telem["a"] = {str(k): float(v) for k, v in msg["a"].items()}
                if "b" in msg and isinstance(msg["b"], dict):
                    self._telem["b"] = {str(k): float(v) for k, v in msg["b"].items()}
                if "max_num_basis" in msg:
                    self._telem["max_num_basis"] = int(msg["max_num_basis"])
                self._last_telem_rx_t = time.monotonic()
            except socket.timeout:
                continue
            except Exception:
                continue
        try:
            sock.close()
        except Exception:
            pass

    def _sync_telemetry_from_bridge_if_local(self) -> None:
        if self.bridge is None or self._remote_bridge:
            return
        try:
            a, b = self.bridge.get_telemetry_snapshot()
            self._telem["a"] = a
            self._telem["b"] = b
            self._telem["max_num_basis"] = int(self.bridge.get_last_max_num_basis())
            if a or b:
                self._last_telem_rx_t = time.monotonic()
        except Exception:
            pass

    def _telemetry_is_fresh(self, timeout_s: float = 1.2) -> bool:
        if self._last_telem_rx_t <= 0.0:
            return False
        return (time.monotonic() - self._last_telem_rx_t) <= timeout_s

    def _read_selected_port_and_baud(self) -> Tuple[str, int]:
        cfg = _simple_yaml_kv_load(self.config_path)
        default_port = str(cfg.get("serial_port", "COM3"))
        default_baud = int(cfg.get("baud_rate", 115200))
        # Manual port input overrides dropdown when non-empty.
        manual_port = str(dpg.get_value("com_manual_input") or "").strip()
        if manual_port:
            sel_port = manual_port
        else:
            sel_port = dpg.get_value("com_selector") or default_port
        sel_baud = dpg.get_value("baud_selector") or default_baud
        if isinstance(sel_baud, str):
            sel_baud = int(sel_baud.strip())
        return str(sel_port), int(sel_baud)

    def _detect_serial_ports(self, fallback: Optional[str] = None) -> Tuple[List[str], Optional[str]]:
        """Return discovered serial ports and optional user-facing error text."""
        default_port = fallback or "COM3"
        try:
            from serial.tools import list_ports  # type: ignore

            ports = [p.device for p in list_ports.comports()]
            # Keep deterministic ordering for readability (COM2, COM3, COM10...).
            ports.sort(key=lambda x: (re.sub(r"\d+", "", x), int(re.findall(r"\d+", x)[0]) if re.findall(r"\d+", x) else 0))
            if default_port not in ports:
                ports.insert(0, default_port)
            return ports or [default_port], None
        except Exception as ex:
            return [default_port], (
                "Could not enumerate serial ports automatically. "
                "Install/check pyserial and use Manual COM if needed. "
                f"Details: {ex}"
            )

    def _show_connection_popup(self, title: str, message: str, is_error: bool) -> None:
        try:
            dpg.set_value("conn_result_text", message)
            dpg.configure_item(
                "conn_result_text",
                color=(220, 70, 70, 255) if is_error else (80, 200, 120, 255),
            )
            dpg.configure_item("conn_result_modal", label=title, show=True)
        except Exception:
            pass

    def _set_connection_detail(self, message: str, is_error: bool = False) -> None:
        try:
            dpg.set_value("conn_detail_text", message)
            dpg.configure_item(
                "conn_detail_text",
                color=(220, 70, 70, 255) if is_error else (170, 190, 220, 255),
            )
        except Exception:
            pass

    def _refresh_com_ports(self) -> None:
        cfg = _simple_yaml_kv_load(self.config_path)
        default_port = str(cfg.get("serial_port", "COM3"))
        ports, err = self._detect_serial_ports(fallback=default_port)
        try:
            current = str(dpg.get_value("com_selector") or "")
        except Exception:
            current = ""
        selected = current if current in ports else (default_port if default_port in ports else ports[0])
        try:
            dpg.configure_item("com_selector", items=ports)
            dpg.set_value("com_selector", selected)
        except Exception:
            pass
        if err is not None:
            self._set_connection_detail(err, is_error=True)
            self._show_connection_popup("Port Scan Warning", err, is_error=True)
        else:
            self._set_connection_detail(f"Detected {len(ports)} port(s): {', '.join(ports)}")

    def _connect_on_launch(self) -> None:
        # Prefer connecting to a running `serial_bridge.py` (simulate mode) if present.
        cfg = _simple_yaml_kv_load(self.config_path)
        self._cmd_host = str(cfg.get("cmd_host", "127.0.0.1"))
        self._cmd_port = int(cfg.get("cmd_udp_port", load_config().get("cmd_udp_port", 1349)))

        if self._try_remote_bridge():
            # Load default preset if present.
            self._load_default_preset_if_exists()
            return

        # Fallback: local SerialBridge (real hardware).
        port, baud = self._read_selected_port_and_baud()
        self._start_bridge(port, baud)
        # Load default preset if present.
        self._load_default_preset_if_exists()

    def _try_remote_bridge(self) -> bool:
        try:
            udp = UdpBridgeClient(self._cmd_host, self._cmd_port)
            if not udp.ping():
                self._last_connect_error = (
                    f"No response from bridge at {self._cmd_host}:{self._cmd_port}. "
                    "Start serial_bridge.py (simulate mode) or use direct serial connection."
                )
                udp.close()
                return False
        except Exception:
            self._last_connect_error = (
                f"Could not contact bridge at {self._cmd_host}:{self._cmd_port}. "
                "Check cmd_host/cmd_udp_port in config.yaml."
            )
            return False

        # Remote bridge is active; don't open local serial.
        try:
            if self.bridge is not None:
                try:
                    self.bridge.stop()
                except Exception:
                    pass
                self.bridge = None
            if self._udp is not None:
                try:
                    self._udp.close()
                except Exception:
                    pass

            self._udp = udp
            self._remote_bridge = True
            self.connected = True
            dpg.configure_item("conn_button", label="Disconnect")
            self._set_connection_detail(f"Connected via UDP bridge {self._cmd_host}:{self._cmd_port}")
            self._show_connection_popup(
                "Connection Established",
                f"Connected to running serial bridge at {self._cmd_host}:{self._cmd_port}.",
                is_error=False,
            )
            self._paths_reset_on_connect()
            return True
        except Exception:
            try:
                udp.close()
            except Exception:
                pass
            self._last_connect_error = "Bridge detected but failed to initialize dashboard UDP client."
            return False

    def _start_bridge(self, port: str, baud: int) -> None:
        try:
            if self.bridge is not None:
                try:
                    self.bridge.stop()
                except Exception:
                    pass
            if self._udp is not None:
                try:
                    self._udp.close()
                except Exception:
                    pass
                self._udp = None

            self._remote_bridge = False
            self.bridge = SerialBridge(serial_port=port, baud_rate=baud)
            self.bridge.start()
            self.connected = True
            dpg.configure_item("conn_button", label="Disconnect")
            self._set_connection_detail(f"Connected on serial {port} @ {baud} bps")
            self._show_connection_popup(
                "Connection Established",
                f"Connected to {port} at {baud} bps.",
                is_error=False,
            )
            self._paths_reset_on_connect()
        except Exception as ex:
            self.connected = False
            self.bridge = None
            dpg.configure_item("conn_button", label="Connect")
            self._last_connect_error = f"Failed to open serial port {port} at {baud} bps: {ex}"
            self._set_connection_detail(self._last_connect_error, is_error=True)
            self._show_connection_popup("Connection Failed", self._last_connect_error, is_error=True)

    def _stop_bridge(self) -> None:
        try:
            if self.bridge is not None:
                self.bridge.stop()
            if self._udp is not None:
                self._udp.close()
        finally:
            self.connected = False
            self.bridge = None
            self._udp = None
            self._remote_bridge = False
            try:
                dpg.configure_item("conn_button", label="Connect")
                self._set_connection_detail("Disconnected")
            except Exception:
                pass

    def _post_ui_call(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        self._ui_actions.put((fn, args, kwargs))

    def _drain_ui_calls(self, max_items: int = 128) -> None:
        for _ in range(max_items):
            try:
                fn, args, kwargs = self._ui_actions.get_nowait()
            except queue.Empty:
                break
            try:
                fn(*args, **kwargs)
            except Exception:
                continue

    def _frame(self) -> None:
        self._drain_ui_calls()
        now = time.monotonic()
        self._sync_telemetry_from_bridge_if_local()
        
        # Smooth high-FPS updates
        if now - self._last_paths_canvas_t >= 0.1:
            self._last_paths_canvas_t = now
            self._update_paths_canvas()
            
        try:
            telem_fresh = self._telemetry_is_fresh()
            a: Dict[str, float] = dict(self._telem.get("a") or {})
            fm_val = -1
            if telem_fresh and "status.flymode" in a:
                fm_val = int(round(float(a.get("status.flymode", -1))))
            
            pulse = (math.sin(now * 6.0) + 1.0) * 0.5  # 0.0 to 1.0
            if fm_val == 1:
                # Pulse bright green if SDK mode active
                dpg.set_value("color_mode_sdk_btn", (0, int(150 + 105 * pulse), 0, 255))
            else:
                dpg.set_value("color_mode_sdk_btn", (60, 60, 60, 255))
            
            if fm_val == 0:
                # Pulse red/orange if Dangerous Stop active
                dpg.set_value("color_mode_stop_btn", (int(180 + 75 * pulse), int(50 * pulse), 0, 255))
            else:
                dpg.set_value("color_mode_stop_btn", (60, 60, 60, 255))
        except Exception:
            pass

        # Run state polling at ~5Hz to keep things cheap.
        if now - self._last_poll_t < 0.2:
            return
        self._last_poll_t = now

        try:
            self._paths_refresh_ui()
        except Exception:
            pass

        if not self.connected:
            try:
                dpg.configure_item("vrc_sdk_btn", enabled=False)
                dpg.configure_item("vrc_arm_req_btn", enabled=False)
                dpg.configure_item("vrc_arm_off_btn", enabled=False)
                dpg.configure_item("btn_mode_sdk", enabled=False)
                dpg.configure_item("btn_mode_stop", enabled=False)
            except Exception:
                pass
            return

        try:
            telem_controls_enabled = self._telemetry_is_fresh()
            dpg.configure_item("vrc_sdk_btn", enabled=telem_controls_enabled)
            dpg.configure_item("vrc_arm_req_btn", enabled=telem_controls_enabled)
            dpg.configure_item("vrc_arm_off_btn", enabled=telem_controls_enabled)
            dpg.configure_item("btn_mode_sdk", enabled=telem_controls_enabled)
            dpg.configure_item("btn_mode_stop", enabled=telem_controls_enabled)
        except Exception:
            pass

        a: Dict[str, float] = dict(self._telem.get("a") or {})
        b: Dict[str, float] = dict(self._telem.get("b") or {})
        telem_fresh = self._telemetry_is_fresh()
        
        if telem_fresh:
            src = "UDP bridge" if self._remote_bridge else "serial"
            self._set_connection_detail(f"Connected ({src}) - telemetry OK")
        else:
            self._set_connection_detail(
                "Connected, but telemetry is stale. Check firmware run state, COM cable, and UART4 @ 115200.",
                is_error=True,
            )

        arm = float(a["status.arm"]) if "status.arm" in a else None
        if arm is not None and self.arm_value_tag is not None:
            arm_on = int(round(arm)) != 0
            dpg.set_value(self.arm_value_tag, "ARM: ON" if arm_on else "ARM: OFF")
            dpg.configure_item(self.arm_value_tag, color=(0, 200, 0, 255) if arm_on else (220, 0, 0, 255))

        sl: Optional[float] = None
        if "status.sbus_lost" in a:
            try:
                sl = float(a["status.sbus_lost"])
            except Exception:
                sl = None
        if sl is not None:
            lost = int(round(sl)) != 0
            dpg.set_value(
                "vrc_source_text",
                "COMPUTER CONTROL" if lost else "RC ACTIVE",
            )
            dpg.configure_item(
                "vrc_source_text",
                color=((80, 160, 255, 255) if lost else (0, 200, 0, 255)),
            )
            for tg in self.vrc_slider_tags:
                dpg.configure_item(tg, enabled=lost)
            if not lost:
                dpg.set_value("vrc_thr_slider", float(RC_STICK_MID))
                dpg.set_value("vrc_pit_slider", float(RC_STICK_MID))
                dpg.set_value("vrc_rol_slider", float(RC_STICK_MID))
                dpg.set_value("vrc_yaw_slider", float(RC_STICK_MID))
        else:
            dpg.set_value("vrc_source_text", "— (no telemetry)")
            dpg.configure_item("vrc_source_text", color=(180, 180, 180, 255))
            for tg in self.vrc_slider_tags:
                dpg.configure_item(tg, enabled=False)

        mb = int(self._telem.get("max_num_basis", 8))
        if mb != self.max_num_basis:
            self.max_num_basis = mb
            self._update_mrac_visibility()

        self._update_monitor_ui(a, b)
        fly_txt = "FlyMode: ?"
        if telem_fresh and "status.flymode" in a:
            try:
                fm = float(a.get("status.flymode", 0.0))
                fm_u8 = int(round(fm))
                if fm_u8 == 1:
                    fly_txt = "FlyMode: SDK"
                elif fm_u8 == 0:
                    fly_txt = "FlyMode: DangerousStop"
                else:
                    fly_txt = f"FlyMode: {fm_u8}"
            except Exception:
                fly_txt = "FlyMode: ?"
        try:
            dpg.set_value("status_fly_sidebar", fly_txt)
        except Exception:
            pass
        sl2: Optional[float] = None
        if telem_fresh and "status.sbus_lost" in a:
            try:
                sl2 = float(a.get("status.sbus_lost", 0.0))
                dpg.set_value(
                    "status_sbus_sidebar",
                    "SBUS: GS" if sl2 >= 0.5 else "SBUS: RC",
                )
            except Exception:
                try:
                    dpg.set_value("status_sbus_sidebar", "SBUS: ?")
                except Exception:
                    pass
        else:
            try:
                dpg.set_value("status_sbus_sidebar", "SBUS: ?")
            except Exception:
                pass
        try:
            dpg.set_value(
                "status_bench_sidebar",
                "Bench: ON" if self._bench_mode_ui else "Bench: OFF",
            )
        except Exception:
            pass
        try:
            arm_u8 = float(a.get("status.arm", 0.0))
            arm_on = int(round(arm_u8)) != 0
            sbus_txt = int(sl2) if sl2 is not None else "?"
            dpg.set_value(
                "mon_footer",
                f"sbus_lost={sbus_txt} | ARM={'ON' if arm_on else 'OFF'} | {fly_txt} | bench={'ON' if self._bench_mode_ui else 'OFF'} | telem={'OK' if telem_fresh else 'STALE'}",
            )
        except Exception:
            pass

        tnow = time.monotonic()
        if self._recording_flight and (tnow - self._last_log_t) >= 0.05:
            self._last_log_t = tnow
            self._flight_logger.log_snapshot("A", a)
            self._flight_logger.log_snapshot("B", b)
        if self._recording_path and (tnow - self._last_path_sample_t) >= 0.1:
            self._last_path_sample_t = tnow
            self._path_point_buffer.append(
                (float(b.get("pid.locx.Des", 0.0)), float(b.get("pid.locy.Des", 0.0)))
            )

    def _paths_refresh_ui(self) -> None:
        try:
            src = str(dpg.get_value("combo_pos_source"))
            self._position_source = src
            ok = src not in ("None", "")
            for tg in ("btn_path_twc_exec", "btn_path_sin_exec", "btn_path_circ_exec"):
                dpg.configure_item(tg, enabled=ok)
        except Exception:
            pass

    def _paths_reset_on_connect(self) -> None:
        self._path_exec_trace.clear()
        try:
            dpg.delete_item("paths_drawlist", children_only=True)
        except Exception:
            pass

    def _paths_world_to_screen(self, wx: float, wy: float) -> Tuple[float, float]:
        # 1 pixel = 0.01 m (100 px/m); canvas center = world origin.
        return (200.0 + wx * 100.0, 200.0 - wy * 100.0)

    def _update_paths_canvas(self) -> None:
        if not self.connected:
            return
        self._sync_telemetry_from_bridge_if_local()
        b: Dict[str, float] = dict(self._telem.get("b") or {})
        if not b:
            return
        fbx = float(b.get("pid.locx.FB", 0.0))
        fby = float(b.get("pid.locy.FB", 0.0))
        self._path_exec_trace.append((fbx, fby))
        if len(self._path_exec_trace) > 4000:
            del self._path_exec_trace[: len(self._path_exec_trace) - 3000]

        twc_tx = float(b.get("path.twc_target_x", 0.0))
        twc_ty = float(b.get("path.twc_target_y", 0.0))
        twc_arr = float(b.get("path.twc_arrived", 0.0))
        mode = int(float(b.get("path.active_path_mode", 0.0)))
        dist = math.hypot(fbx - twc_tx, fby - twc_ty)
        try:
            dpg.set_value("txt_path_twc_dist", f"Distance: {dist:.2f} m")
            dpg.configure_item(
                "txt_path_twc_dist",
                color=(0, 200, 80, 255) if twc_arr >= 0.5 else (210, 210, 210, 255),
            )
        except Exception:
            pass

        try:
            dpg.delete_item("paths_drawlist", children_only=True)
        except Exception:
            return

        dl = "paths_drawlist"
        grey = (140, 140, 150, 255)
        dpg.draw_line((0.0, 200.0), (400.0, 200.0), color=grey, thickness=1, parent=dl)
        dpg.draw_line((200.0, 0.0), (200.0, 400.0), color=grey, thickness=1, parent=dl)

        def _blue_plan(pts: List[Tuple[float, float]]) -> None:
            if len(pts) < 2:
                return
            for i in range(len(pts) - 1):
                x1, y1 = self._paths_world_to_screen(pts[i][0], pts[i][1])
                x2, y2 = self._paths_world_to_screen(pts[i + 1][0], pts[i + 1][1])
                dpg.draw_line((x1, y1), (x2, y2), color=(80, 120, 255, 255), thickness=2, parent=dl)

        try:
            tcx = float(dpg.get_value("twc_tx"))
            tcy = float(dpg.get_value("twc_ty"))
            cxs = float(dpg.get_value("sin_cx"))
            cys = float(dpg.get_value("sin_cy"))
            amp = float(dpg.get_value("sin_amp"))
            axs = int(float(dpg.get_value("sin_axis")))
            crc = float(dpg.get_value("cir_cx"))
            cry = float(dpg.get_value("cir_cy"))
            crd = float(dpg.get_value("cir_r"))
        except Exception:
            tcx = tcy = cxs = cys = amp = crc = cry = crd = 0.0
            axs = 0

        nseg = 48
        u = [2.0 * math.pi * i / (nseg - 1) for i in range(nseg)]
        if mode == 0 or mode == 1:
            _blue_plan([(fbx, fby), (tcx, tcy)])
        if mode == 2:
            pts: List[Tuple[float, float]] = []
            for i in u:
                si = amp * math.sin(i)
                if axs == 0:
                    pts.append((cxs + si, cys))
                elif axs == 1:
                    pts.append((cxs, cys + si))
                else:
                    pts.append((cxs + 0.15 * math.cos(i), cys + 0.15 * math.sin(i)))
            _blue_plan(pts)
        if mode == 3:
            pts2: List[Tuple[float, float]] = []
            for i in range(33):
                ang = 2.0 * math.pi * i / 32.0
                pts2.append((crc + crd * math.cos(ang), cry + crd * math.sin(ang)))
            _blue_plan(pts2)

        if len(self._path_exec_trace) >= 2:
            for i in range(len(self._path_exec_trace) - 1):
                x1, y1 = self._paths_world_to_screen(self._path_exec_trace[i][0], self._path_exec_trace[i][1])
                x2, y2 = self._paths_world_to_screen(
                    self._path_exec_trace[i + 1][0], self._path_exec_trace[i + 1][1]
                )
                dpg.draw_line((x1, y1), (x2, y2), color=(40, 220, 90, 200), thickness=2, parent=dl)

        cx, cy = self._paths_world_to_screen(fbx, fby)
        dpg.draw_circle((cx, cy), 6.0, color=(30, 200, 70, 255), fill=(30, 200, 70, 255), parent=dl)

        if mode == 1 or abs(twc_tx) + abs(twc_ty) > 1e-6:
            tx, ty = self._paths_world_to_screen(twc_tx, twc_ty)
            s = 8.0
            dpg.draw_line((tx - s, ty - s), (tx + s, ty + s), color=(255, 60, 60, 255), thickness=2, parent=dl)
            dpg.draw_line((tx - s, ty + s), (tx + s, ty - s), color=(255, 60, 60, 255), thickness=2, parent=dl)

    def _paths_cmd_twc(self) -> None:
        self._path_abort_flag[0] = False
        try:
            x = float(dpg.get_value("twc_tx"))
            y = float(dpg.get_value("twc_ty"))
            z = float(dpg.get_value("twc_tz"))
            yaw = float(dpg.get_value("twc_yaw"))
        except Exception:
            return
        self._send_cmd(0x0A, 0, x)
        self._send_cmd(0x0A, 1, y)
        self._send_cmd(0x0A, 2, z)
        self._send_cmd(0x0A, 3, yaw)
        self._send_cmd(0x0A, 4, 1.0)

    def _paths_cmd_sinusoid(self) -> None:
        self._path_abort_flag[0] = False
        try:
            cx = float(dpg.get_value("sin_cx"))
            cy = float(dpg.get_value("sin_cy"))
            cz = float(dpg.get_value("sin_cz"))
            amp = float(dpg.get_value("sin_amp"))
            fq = float(dpg.get_value("sin_freq"))
            dur = float(dpg.get_value("sin_dur"))
            axis = float(dpg.get_value("sin_axis"))
        except Exception:
            return
        self._send_cmd(0x0B, 0, cx)
        self._send_cmd(0x0B, 1, cy)
        self._send_cmd(0x0B, 2, cz)
        self._send_cmd(0x0B, 3, amp)
        self._send_cmd(0x0B, 4, fq)
        self._send_cmd(0x0B, 5, dur)
        self._send_cmd(0x0B, 6, axis)
        self._send_cmd(0x0B, 7, 1.0)

    def _paths_cmd_circle(self) -> None:
        self._path_abort_flag[0] = False
        try:
            cx = float(dpg.get_value("cir_cx"))
            cy = float(dpg.get_value("cir_cy"))
            cz = float(dpg.get_value("cir_cz"))
            r = float(dpg.get_value("cir_r"))
            om = float(dpg.get_value("cir_omega"))
            dur = float(dpg.get_value("cir_dur"))
        except Exception:
            return
        self._send_cmd(0x0C, 0, cx)
        self._send_cmd(0x0C, 1, cy)
        self._send_cmd(0x0C, 2, cz)
        self._send_cmd(0x0C, 3, r)
        self._send_cmd(0x0C, 4, om)
        self._send_cmd(0x0C, 5, dur)
        self._send_cmd(0x0C, 6, 1.0)

    def _paths_clear_trace(self) -> None:
        self._path_exec_trace.clear()
        try:
            dpg.delete_item("paths_drawlist", children_only=True)
        except Exception:
            pass

    def _update_mrac_visibility(self) -> None:
        # Hide sliders where i >= MAX_NUM_BASIS.
        for axis, kind, i, tag in self.mrac_slider_tags:
            show = i < self.max_num_basis
            try:
                dpg.configure_item(tag, show=show)
            except Exception:
                pass

    def _send_cmd(self, cmd_id: int, index: int, value: float, *, force: bool = False) -> None:
        if not force and not self.connected:
            return
        if self._remote_bridge:
            if self._udp is None:
                return
            self._udp.send_cmd(cmd_id, index, value)
            return
        # Local in-process bridge (hardware mode).
        from ground_station.comm.serial_bridge import cmd_queue

        if self.bridge is None:
            return
        cmd_queue.put({"cmd_id": cmd_id, "index": index, "value": float(value)})

    def _emergency_stop(self) -> None:
        """Abort paths (0x0D) then dangerous stop (0x04), 50 ms apart."""
        self._path_abort_flag[0] = True
        self._send_cmd(0x0D, 0, 1.0, force=True)

        def _late_stop() -> None:
            self._send_cmd(0x04, 0, 0.0, force=True)

        threading.Timer(0.05, _late_stop).start()

    def _debounced_pid_gain(self, axis: str, pid_type: str, gain_name: str, value: float) -> None:
        pids_axis = OUTER_PID_AXIS_TO_PIDS[axis] if pid_type == "outer" else INNER_PID_AXIS_TO_PIDS[axis]
        gain_idx = PID_GAIN_IDXS[gain_name]
        index = (pids_axis * 3) + gain_idx  # firmware uses idx/3 for axis, idx%3 for Kp/Ki/Kd
        key = f"pid:{axis}:{pid_type}:{gain_name}"
        self._debouncer.call(key, self._send_cmd, 0x01, index, value)

    def _debounced_z_rate_pid_gain(self, gain_name: str, value: float) -> None:
        """Single Z-rate PID (firmware axis index 6). CMD 0x01 index = 6*3 + gain."""
        gain_idx = PID_GAIN_IDXS[gain_name]
        index = (Z_RATE_PID_INDEX * 3) + gain_idx
        key = f"pid:z:z_rate:{gain_name}"
        self._debouncer.call(key, self._send_cmd, 0x01, index, value)

    def _debounced_mrac_param(self, axis: str, kind: str, i: int, value: float) -> None:
        axis_cfg_idx = AXES[axis]  # pitch=0, roll=1, yaw=2, z=3
        index = ((axis_cfg_idx & 0x0F) << 4) | (i & 0x0F)
        if kind == "gamma":
            cmd_id = 0x02
        elif kind == "What_limit":
            cmd_id = 0x05
        elif kind == "What_tol":
            cmd_id = 0x08
        else:
            cmd_id = 0x02
        key = f"mrac:{axis}:{kind}:{i}"
        self._debouncer.call(key, self._send_cmd, cmd_id, index, value)

    def _debounced_mixer(self, axis: str, field: str, value: float) -> None:
        axis_cfg_idx = AXES[axis]
        if field == "MRAC_TO_MIXER":
            index = axis_cfg_idx  # idx 0..3
        else:
            index = axis_cfg_idx + 4  # idx 4..7
        key = f"mixer:{axis}:{field}"
        self._debouncer.call(key, self._send_cmd, 0x03, index, value)

    def _on_outer_pid_slider(self, sender: Any, app_data: Any, user_data: Any) -> None:
        if self._loading_preset:
            return
        axis, gain_name = user_data
        self._debounced_pid_gain(axis, "outer", gain_name, float(app_data))

    def _on_inner_pid_slider(self, sender: Any, app_data: Any, user_data: Any) -> None:
        if self._loading_preset:
            return
        axis, gain_name = user_data
        self._debounced_pid_gain(axis, "inner", gain_name, float(app_data))

    def _on_z_rate_pid_slider(self, sender: Any, app_data: Any, user_data: Any) -> None:
        if self._loading_preset:
            return
        gain_name = str(user_data)
        self._debounced_z_rate_pid_gain(gain_name, float(app_data))

    def _on_mrac_slider(self, sender: Any, app_data: Any, user_data: Any) -> None:
        if self._loading_preset:
            return
        axis, kind, i = user_data
        self._debounced_mrac_param(axis, kind, int(i), float(app_data))

    def _on_mixer_slider(self, sender: Any, app_data: Any, user_data: Any) -> None:
        if self._loading_preset:
            return
        axis, field = user_data
        self._debounced_mixer(axis, field, float(app_data))

    def _on_connect_disconnect(self) -> None:
        if self.connected:
            self._stop_bridge()
            self._show_connection_popup("Disconnected", "Connection closed.", is_error=False)
        else:
            cfg = _simple_yaml_kv_load(self.config_path)
            self._cmd_host = str(cfg.get("cmd_host", "127.0.0.1"))
            self._cmd_port = int(cfg.get("cmd_udp_port", load_config().get("cmd_udp_port", 1349)))
            if self._try_remote_bridge():
                self._load_default_preset_if_exists()
                return
            port, baud = self._read_selected_port_and_baud()
            self._start_bridge(port, baud)
            self._load_default_preset_if_exists()

    def _default_slider_mid(self, mn: float, mx: float) -> float:
        return (mn + mx) * 0.5

    def _set_slider_value(self, tag: Any, value: float) -> None:
        # DearPyGui clamps internally, but we clamp here for nicer preset semantics.
        try:
            dpg.set_value(tag, value)
        except Exception:
            pass

    def _load_default_preset_if_exists(self) -> None:
        self._loading_preset = True
        try:
            default_path = self.presets_dir / "default.yaml"
            if not default_path.exists():
                self._set_to_midpoints()
                return
            preset = load_preset_yaml(default_path)
            self._apply_preset_payload(preset)
        finally:
            self._loading_preset = False

    def _set_to_midpoints(self) -> None:
        for axis in ["pitch", "roll", "yaw", "z"]:
            if axis != "z":
                self._set_slider_value(self.outer_pid[axis]["Kp"], self._default_slider_mid(0.0, 10.0))
                self._set_slider_value(self.outer_pid[axis]["Ki"], self._default_slider_mid(0.0, 1.0))
                self._set_slider_value(self.outer_pid[axis]["Kd"], self._default_slider_mid(0.0, 5.0))
            # Inner (pitch/roll/yaw rate) or sole Z rate PID
            self._set_slider_value(self.inner_pid[axis]["Kp"], self._default_slider_mid(0.0, 20.0))
            self._set_slider_value(self.inner_pid[axis]["Ki"], self._default_slider_mid(0.0, 0.5))
            self._set_slider_value(self.inner_pid[axis]["Kd"], self._default_slider_mid(0.0, 2.0))

            # MRAC
            for i in range(8):
                self._set_slider_value(self.mrac_gamma[axis][i], 1.0)
                self._set_slider_value(self.mrac_what_limit[axis][i], 1.0)
                self._set_slider_value(self.mrac_what_tol[axis][i], 0.1)

            # Mixer/Saturation
            self._set_slider_value(self.mixer_slider[axis], 500.0)
            self._set_slider_value(self.u_max_slider[axis], 10.0)

    def _apply_preset_payload(self, preset: Dict[str, Any]) -> None:
        # axis: pitch/roll/yaw/z
        for axis in ["pitch", "roll", "yaw", "z"]:
            axis_payload = preset.get(axis, {})

            outer_pid = axis_payload.get("outer_pid", {})
            if axis != "z" and outer_pid:
                for gain in ["Kp", "Ki", "Kd"]:
                    if gain in outer_pid:
                        self._set_slider_value(self.outer_pid[axis][gain], float(outer_pid[gain]))

            inner_pid = axis_payload.get("inner_pid", {})
            if inner_pid:
                for gain in ["Kp", "Ki", "Kd"]:
                    if gain in inner_pid:
                        self._set_slider_value(self.inner_pid[axis][gain], float(inner_pid[gain]))

            mrac = axis_payload.get("mrac", {})
            if mrac:
                gamma = mrac.get("gamma", [])
                wl = mrac.get("What_limit", [])
                wt = mrac.get("What_tol", [])
                for i in range(8):
                    if i < len(gamma):
                        self._set_slider_value(self.mrac_gamma[axis][i], float(gamma[i]))
                    if i < len(wl):
                        self._set_slider_value(self.mrac_what_limit[axis][i], float(wl[i]))
                    if i < len(wt):
                        self._set_slider_value(self.mrac_what_tol[axis][i], float(wt[i]))

            mixer = axis_payload.get("mixer", {})
            if mixer:
                if "MRAC_TO_MIXER" in mixer:
                    self._set_slider_value(self.mixer_slider[axis], float(mixer["MRAC_TO_MIXER"]))
                if "U_MAX" in mixer:
                    self._set_slider_value(self.u_max_slider[axis], float(mixer["U_MAX"]))

        # Update MRAC hide/show after preset.
        self._update_mrac_visibility()

    def _collect_preset_payload(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for axis in ["pitch", "roll", "yaw", "z"]:
            inner_pid = {gain: float(dpg.get_value(self.inner_pid[axis][gain])) for gain in ["Kp", "Ki", "Kd"]}
            mrac = {
                "gamma": [float(dpg.get_value(self.mrac_gamma[axis][i])) for i in range(8)],
                "What_limit": [float(dpg.get_value(self.mrac_what_limit[axis][i])) for i in range(8)],
                "What_tol": [float(dpg.get_value(self.mrac_what_tol[axis][i])) for i in range(8)],
            }
            mixer = {
                "MRAC_TO_MIXER": float(dpg.get_value(self.mixer_slider[axis])),
                "U_MAX": float(dpg.get_value(self.u_max_slider[axis])),
            }
            if axis == "z":
                out[axis] = {"inner_pid": inner_pid, "mrac": mrac, "mixer": mixer}
            else:
                out[axis] = {
                    "outer_pid": {gain: float(dpg.get_value(self.outer_pid[axis][gain])) for gain in ["Kp", "Ki", "Kd"]},
                    "inner_pid": inner_pid,
                    "mrac": mrac,
                    "mixer": mixer,
                }
        return out

    def _save_preset_to_name(self, name: str) -> None:
        safe = re.sub(r"[^a-zA-Z0-9_.-]", "_", name).strip("._-")
        if not safe:
            return
        payload = self._collect_preset_payload()
        out_path = self.presets_dir / f"{safe}.yaml"
        dump_preset_yaml(out_path, payload)
        self._current_preset_label = safe
        try:
            dpg.set_value("txt_preset_name", safe)
            self._refresh_preset_list()
            dpg.set_value("combo_preset_pick", safe)
        except Exception:
            pass

    def _load_preset_from_file(self, path: Path) -> None:
        self._loading_preset = True
        try:
            preset = load_preset_yaml(path)
            self._apply_preset_payload(preset)
            self._current_preset_label = path.stem
            try:
                dpg.set_value("txt_preset_name", path.stem)
                dpg.set_value("combo_preset_pick", path.stem)
            except Exception:
                pass
        finally:
            self._loading_preset = False

    def _browse_and_load_preset(self) -> None:
        # Uses tkinter for reliable file picking.
        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            file_path = filedialog.askopenfilename(
                initialdir=str(self.presets_dir),
                title="Select preset YAML",
                filetypes=[("YAML files", "*.yaml;*.yml"), ("All files", "*.*")],
            )
            if not file_path:
                return
            self._load_preset_from_file(Path(file_path))
        except Exception:
            return

    def _refresh_preset_list(self) -> None:
        try:
            items = sorted([p.stem for p in self.presets_dir.glob("*.yaml")])
            if not items:
                items = ["(no presets)"]
            dpg.configure_item("combo_preset_pick", items=items)
        except Exception:
            pass

    def _on_pick_preset(self, sender: Any, app_data: Any) -> None:
        name = str(app_data or "").strip()
        if not name or name.startswith("("):
            return
        path = self.presets_dir / f"{name}.yaml"
        if path.exists():
            self._load_preset_from_file(path)
            self._current_preset_label = name
            try:
                dpg.set_value("txt_preset_name", name)
            except Exception:
                pass

    def _persist_vofa_executable(self, path_str: str) -> None:
        self._vofa_executable = path_str
        try:
            cfg = _simple_yaml_kv_load(self.config_path)
            if str(cfg.get("vofa_executable", "")).strip() == path_str:
                return
            cfg["vofa_executable"] = path_str
            _simple_yaml_kv_write(self.config_path, cfg)
        except Exception:
            return

    def _discover_vofa_install_path(self) -> Optional[str]:
        exe_names = [
            "VOFA+.exe",
            "vofa+.exe",
            "VOFA.exe",
            "vofa.exe",
        ]

        for cmd in ["vofa+", "VOFA+", "vofa", "VOFA"]:
            found = shutil.which(cmd)
            if found and Path(found).exists():
                return str(Path(found).resolve())

        roots: List[Path] = []
        for env_name in ["ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA", "APPDATA", "USERPROFILE"]:
            raw = os.environ.get(env_name)
            if raw:
                roots.append(Path(raw))

        home = Path.home()
        roots.extend(
            [
                home,
                home / "Desktop",
                home / "Documents",
                home / "Downloads",
            ]
        )

        rel_dirs = [
            Path("VOFA+"),
            Path("VOFA"),
            Path("Programs") / "VOFA+",
            Path("Programs") / "VOFA",
        ]

        seen: set[str] = set()
        for root in roots:
            root_str = str(root)
            if not root_str or root_str in seen:
                continue
            seen.add(root_str)
            for rel in rel_dirs:
                for exe_name in exe_names:
                    p = root / rel / exe_name
                    if p.exists():
                        return str(p.resolve())
        return None

    def _ensure_vofa_executable(self) -> Optional[str]:
        if self._vofa_executable and Path(self._vofa_executable).exists():
            return self._vofa_executable

        cfg = _simple_yaml_kv_load(self.config_path)
        configured = cfg.get("vofa_executable")
        if isinstance(configured, str) and configured and Path(configured).exists():
            self._vofa_executable = configured
            return configured

        discovered = self._discover_vofa_install_path()
        if discovered:
            self._persist_vofa_executable(discovered)
            return discovered

        return None

    def _resolve_vofa_workspace_path(self, workspace_rel: str) -> Path:
        """Resolve VOFA workspace path across legacy .vofa and newer .tabviews.json formats."""
        p = (self.repo_root / workspace_rel).resolve()
        if p.exists():
            return p

        candidates: List[Path] = []
        if p.suffix.lower() == ".vofa":
            # VOFA 1.3+ saves layout files as tabviews JSON.
            candidates.append(p.with_suffix(".tabviews.json"))
            candidates.append(p.with_suffix(".json"))
            # If user typed "name.vofa" in save dialog, VOFA may append ".tabviews.json".
            candidates.append(p.with_name(p.name + ".tabviews.json"))

        for c in candidates:
            if c.exists():
                return c
        return p

    def _get_vofa_stream_port(self, stream: str) -> int:
        cfg = _simple_yaml_kv_load(self.config_path)
        if stream.lower().strip() == "b":
            raw = cfg.get("vofa_port_b", cfg.get("vofa_port", 1348))
        else:
            raw = cfg.get("vofa_port_a", cfg.get("vofa_port", 1347))
        try:
            return int(raw)
        except Exception:
            return 1348 if stream.lower().strip() == "b" else 1347

    def _get_latest_vofa_context_file(
        self, file_name: str, local_app_override: Optional[Path] = None
    ) -> Optional[Path]:
        if local_app_override is not None:
            root = local_app_override / "vofa+"
        else:
            local_app = os.environ.get("LOCALAPPDATA")
            if not local_app:
                return None
            root = Path(local_app) / "vofa+"
        if not root.exists():
            return None

        candidates = list(root.glob(f"*/context/{file_name}"))
        if not candidates:
            return None

        def _ver_key(p: Path) -> int:
            try:
                return int(p.parents[1].name)
            except Exception:
                return -1

        candidates.sort(key=_ver_key, reverse=True)
        return candidates[0]

    def _get_vofa_context_config_path(self, local_app_override: Optional[Path] = None) -> Optional[Path]:
        return self._get_latest_vofa_context_file("vofa+.config.json", local_app_override)

    def _get_vofa_context_tabviews_path(self, local_app_override: Optional[Path] = None) -> Optional[Path]:
        return self._get_latest_vofa_context_file("vofa+.tabviews.json", local_app_override)

    def _get_vofa_context_dir(self, local_app_override: Optional[Path] = None) -> Optional[Path]:
        if local_app_override is not None:
            base = local_app_override
        else:
            local_app = os.environ.get("LOCALAPPDATA")
            if not local_app:
                return None
            base = Path(local_app)

        root = base / "vofa+"
        try:
            root.mkdir(parents=True, exist_ok=True)
        except Exception:
            return None

        versions = [p for p in root.iterdir() if p.is_dir() and p.name.isdigit()]
        if versions:
            versions.sort(key=lambda p: int(p.name), reverse=True)
            ver_dir = versions[0]
        else:
            ver_dir = root / "100"
            try:
                ver_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                return None

        context_dir = ver_dir / "context"
        try:
            context_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            return None
        return context_dir

    def _infer_stream_from_context_cfg(self, context_cfg: Optional[Path]) -> Optional[str]:
        if context_cfg is None or not context_cfg.exists():
            return None
        try:
            payload = json.loads(context_cfg.read_text(encoding="utf-8"))
        except Exception:
            return None

        found_ports: set[int] = set()

        def _walk(node: Any) -> None:
            if isinstance(node, dict):
                udp = node.get("udp")
                if isinstance(udp, dict):
                    try:
                        found_ports.add(int(udp.get("local_port")))
                    except Exception:
                        pass
                for v in node.values():
                    _walk(v)
            elif isinstance(node, list):
                for v in node:
                    _walk(v)

        _walk(payload)
        if not found_ports:
            return None

        port_a = self._get_vofa_stream_port("a")
        port_b = self._get_vofa_stream_port("b")
        has_a = port_a in found_ports
        has_b = port_b in found_ports
        if has_a and not has_b:
            return "a"
        if has_b and not has_a:
            return "b"
        return None

    def _sync_system_context_to_stream_cache(self, stream: str) -> None:
        stream_key = "b" if stream.lower().strip() == "b" else "a"
        cache_local_app = self._vofa_runtime_root / stream_key / "localappdata"
        cache_context = self._get_vofa_context_dir(cache_local_app)
        if cache_context is None:
            return

        system_cfg = self._get_vofa_context_config_path()
        system_tabviews = self._get_vofa_context_tabviews_path()
        if system_cfg is not None and system_cfg.exists():
            try:
                shutil.copy2(system_cfg, cache_context / "vofa+.config.json")
            except Exception:
                pass
        if system_tabviews is not None and system_tabviews.exists():
            try:
                shutil.copy2(system_tabviews, cache_context / "vofa+.tabviews.json")
            except Exception:
                pass

    def _stage_stream_cache_to_system_context(self, local_app_root: Path) -> None:
        source_context = self._get_vofa_context_dir(local_app_root)
        target_context = self._get_vofa_context_dir()
        if target_context is None or source_context is None or not source_context.exists():
            return

        for name in ["vofa+.config.json", "vofa+.tabviews.json"]:
            src = source_context / name
            dst = target_context / name
            if not src.exists():
                continue
            try:
                shutil.copy2(src, dst)
            except Exception:
                continue

    def _ensure_vofa_stream_context(
        self, stream: str, workspace_path: Path, manual_mode: bool
    ) -> Path:
        stream_key = "b" if stream.lower().strip() == "b" else "a"
        local_app_root = self._vofa_runtime_root / stream_key / "localappdata"
        context_dir = self._get_vofa_context_dir(local_app_root)
        if context_dir is None:
            return local_app_root

        target_cfg = context_dir / "vofa+.config.json"
        target_tabviews = context_dir / "vofa+.tabviews.json"

        if not target_cfg.exists():
            # Seed from immutable per-stream baseline — never from mutable system config.
            baseline = self.repo_root / "presets" / "vofa" / f"baseline_{stream_key}.config.json"
            if baseline.exists():
                shutil.copy2(baseline, target_cfg)
            else:
                target_cfg.write_text("{}", encoding="utf-8")

        # Contamination guard: repair settings_ctx schema if it belongs to the wrong stream.
        baseline = self.repo_root / "presets" / "vofa" / f"baseline_{stream_key}.config.json"
        if target_cfg.exists() and baseline.exists():
            try:
                payload = json.loads(target_cfg.read_text(encoding="utf-8"))
                sp = payload["ctx"]["wave_view"]["ctx"]["settingsPanel"]["ctx"]["."]
                first_name = (sp.get("settings_ctx") or [{}])[0].get("name", "")
                a_fingerprint = first_name.startswith("mrac_pitch_e") or first_name.startswith("mrac_roll_e")
                b_fingerprint = first_name.startswith("mrac_pitch_theta") or first_name.startswith("mrac_roll_theta")
                contaminated = (stream_key == "a" and b_fingerprint) or (stream_key == "b" and a_fingerprint)
                if contaminated:
                    # Repair settings_ctx from baseline; keep tabviews untouched.
                    bl = json.loads(baseline.read_text(encoding="utf-8"))
                    sp["settings_ctx"] = bl["ctx"]["wave_view"]["ctx"]["settingsPanel"]["ctx"]["."]["settings_ctx"]
                    target_cfg.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass

        if not target_tabviews.exists():
            if workspace_path.exists():
                target_tabviews.write_text(workspace_path.read_text(encoding="utf-8"), encoding="utf-8")
            else:
                src_tabviews = self._get_vofa_context_tabviews_path()
                if src_tabviews is not None and src_tabviews.exists():
                    shutil.copy2(src_tabviews, target_tabviews)
                else:
                    target_tabviews.write_text("{}", encoding="utf-8")

        if not manual_mode and workspace_path.exists():
            target_tabviews.write_text(workspace_path.read_text(encoding="utf-8"), encoding="utf-8")

        return local_app_root

    def _prepare_vofa_runtime(self, local_port: int, context_cfg: Optional[Path] = None) -> None:
        if context_cfg is None:
            context_cfg = self._get_vofa_context_config_path()
        if context_cfg is None or not context_cfg.exists():
            return

        try:
            payload = json.loads(context_cfg.read_text(encoding="utf-8"))
        except Exception:
            return

        cfg = _simple_yaml_kv_load(self.config_path)
        vofa_host = str(cfg.get("vofa_host", "127.0.0.1"))

        # VOFA can keep multiple profile trees in one config; patch all of them.
        touched = False

        def _walk(node: Any) -> None:
            nonlocal touched
            if isinstance(node, dict):
                udp = node.get("udp")
                if isinstance(udp, dict):
                    udp["remote_ip"] = vofa_host
                    udp["local_port"] = str(int(local_port))
                    udp["remote_port"] = str(int(local_port))
                    touched = True

                if "protocol_combo" in node:
                    node["protocol_combo"] = "JustFloat"
                    touched = True
                if "link_type_combo" in node:
                    node["link_type_combo"] = 1
                    touched = True

                for v in node.values():
                    _walk(v)
            elif isinstance(node, list):
                for v in node:
                    _walk(v)

        _walk(payload)

        if not touched:
            return

        try:
            context_cfg.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except Exception:
            return

    def _apply_vofa_workspace_to_context(
        self, workspace_path: Path, context_tabviews: Optional[Path] = None
    ) -> bool:
        if not workspace_path.exists():
            return False
        if context_tabviews is None:
            context_tabviews = self._get_vofa_context_tabviews_path()
        if context_tabviews is None:
            return False
        try:
            # VOFA 1.3.x restores layout from this context file on startup.
            context_tabviews.write_text(workspace_path.read_text(encoding="utf-8"), encoding="utf-8")
            return True
        except Exception:
            return False

    def _build_frame_a_channel_names(self) -> List[str]:
        return [
            "mrac_pitch_e",
            "mrac_pitch_u_ad",
            "mrac_roll_e",
            "mrac_roll_u_ad",
            "mrac_yaw_e",
            "mrac_yaw_u_ad",
            "mrac_z_e",
            "mrac_z_u_ad",
            "status_arm",
            "status_flymode",
            "status_sbus_lost",
            "status_twc_execute",
            "status_twc_arrived",
        ]

    def _build_frame_b_channel_names(self, max_num_basis: int) -> List[str]:
        mb = max(1, min(32, int(max_num_basis)))
        names: List[str] = []
        for axis in ["pitch", "roll", "yaw", "z"]:
            for i in range(mb):
                names.append(f"mrac_{axis}_theta_{i}")
            names.append(f"mrac_{axis}_u_nom")
            names.append(f"mrac_{axis}_xm")

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
            names.append(f"pid_{loop}_FB")
            names.append(f"pid_{loop}_Des")
            names.append(f"pid_{loop}_U")

        names.extend(
            [
                "path_active_path_mode",
                "path_twc_target_x",
                "path_twc_target_y",
                "path_twc_target_z",
                "path_sinusoid_t_elapsed",
                "path_circle_theta",
                "path_twc_arrived",
            ]
        )
        return names

    def _extract_vofa_workspace_lines(self, workspace_path: Path) -> List[int]:
        try:
            payload = json.loads(workspace_path.read_text(encoding="utf-8"))
        except Exception:
            return []

        out: set[int] = set()
        roots = payload.get("ctx", [])
        if not isinstance(roots, list):
            return []

        for root in roots:
            if not isinstance(root, dict):
                continue
            tabs = root.get("tabs", [])
            if not isinstance(tabs, list):
                continue
            for tab in tabs:
                if not isinstance(tab, dict):
                    continue
                widgets = tab.get("widgets", [])
                if not isinstance(widgets, list):
                    continue
                for widget in widgets:
                    if not isinstance(widget, dict):
                        continue
                    wctx = widget.get("ctx", {})
                    if not isinstance(wctx, dict):
                        continue
                    lines = (
                        wctx.get("rbw", {})
                        .get("ctx", {})
                        .get(".", {})
                        .get("lines", [])
                    )
                    if not isinstance(lines, list):
                        continue
                    for line_idx in lines:
                        try:
                            idx = int(line_idx)
                        except Exception:
                            continue
                        if idx >= 0:
                            out.add(idx)
        return sorted(out)

    def _infer_max_num_basis(self) -> int:
        try:
            mb = int(self._telem.get("max_num_basis", 6))
        except Exception:
            mb = 6
        return max(1, min(32, mb))

    def _apply_vofa_channel_labels(
        self, stream: str, workspace_path: Path, context_cfg: Optional[Path] = None
    ) -> None:
        if context_cfg is None:
            context_cfg = self._get_vofa_context_config_path()
        if context_cfg is None or not context_cfg.exists():
            return

        if stream.lower().strip() == "b":
            names = self._build_frame_b_channel_names(self._infer_max_num_basis())
        else:
            names = self._build_frame_a_channel_names()

        visible_lines = self._extract_vofa_workspace_lines(workspace_path)
        line_set = set(visible_lines)

        try:
            payload = json.loads(context_cfg.read_text(encoding="utf-8"))
        except Exception:
            return

        touched = False

        def _walk(node: Any) -> None:
            nonlocal touched
            if isinstance(node, dict):
                if isinstance(node.get("settings_ctx"), list):
                    old_list = node.get("settings_ctx", [])
                    if not isinstance(old_list, list):
                        old_list = []
                    max_idx = max(line_set) if line_set else (len(names) - 1)
                    count = max(len(names), max_idx + 1, len(old_list))
                    new_list: List[Dict[str, Any]] = []
                    for i in range(count):
                        old = old_list[i] if i < len(old_list) and isinstance(old_list[i], dict) else {}
                        display_name = names[i] if i < len(names) else f"I{i}"
                        new_list.append(
                            {
                                "is_draw": bool(i in line_set) if line_set else bool(old.get("is_draw", True)),
                                "color": old.get("color", "#ffffff"),
                                "scale": old.get("scale", 1),
                                "yoffset": old.get("yoffset", 0),
                                "xoffset": old.get("xoffset", 0),
                                "decimal": old.get("decimal", -7),
                                "value": old.get("value", 0),
                                "name": display_name,
                            }
                        )
                    node["settings_ctx"] = new_list
                    touched = True

                for v in node.values():
                    _walk(v)
            elif isinstance(node, list):
                for v in node:
                    _walk(v)

        _walk(payload)
        if not touched:
            return

        try:
            context_cfg.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except Exception:
            return

    def _terminate_vofa_stream(self, stream: str) -> None:
        """Kill only the target stream's VOFA process, leaving the other stream alive."""
        stream_key = "b" if stream.lower().strip() == "b" else "a"
        proc = self._vofa_procs.get(stream_key)
        if proc is not None and proc.poll() is None:
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
                proc.wait(timeout=3)
            except Exception:
                pass
        self._vofa_procs[stream_key] = None
        time.sleep(0.3)

    def _terminate_vofa_instances(self, vofa_exe: str, force: bool = True) -> None:
        exe_name = Path(vofa_exe).name
        if not exe_name:
            return

        # Try graceful close first so VOFA can persist user edits.
        try:
            subprocess.run(
                ["taskkill", "/T", "/IM", exe_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception:
            pass

        time.sleep(0.4)

        if force:
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/IM", exe_name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            except Exception:
                pass

        self._vofa_procs["a"] = None
        self._vofa_procs["b"] = None
        # Give VOFA a brief moment to fully release UDP bind state.
        time.sleep(0.25)

    def _get_vofa_stream_preset_dir(self, stream: str) -> Path:
        stream_key = "b" if stream.lower().strip() == "b" else "a"
        return self.repo_root / "presets" / "vofa" / f"stream_{stream_key}"

    def _get_stream_expected_channel_names(self, stream: str) -> List[str]:
        stream_key = "b" if stream.lower().strip() == "b" else "a"
        if stream_key == "b":
            # Frame B presets are fixed for MAX_NUM_BASIS=6.
            return self._build_frame_b_channel_names(6)
        return self._build_frame_a_channel_names()

    def _repair_stream_config_channel_names(self, stream: str, context_cfg: Path) -> None:
        if not context_cfg.exists():
            return

        expected_names = self._get_stream_expected_channel_names(stream)

        try:
            payload = json.loads(context_cfg.read_text(encoding="utf-8"))
        except Exception:
            return

        touched = False

        def _walk(node: Any) -> None:
            nonlocal touched
            if isinstance(node, dict):
                settings_ctx = node.get("settings_ctx")
                if isinstance(settings_ctx, list):
                    rebuilt: List[Dict[str, Any]] = []
                    for i, display_name in enumerate(expected_names):
                        old = settings_ctx[i] if i < len(settings_ctx) and isinstance(settings_ctx[i], dict) else {}
                        rebuilt.append(
                            {
                                "is_draw": bool(old.get("is_draw", True)),
                                "color": old.get("color", "#ffffff"),
                                "scale": old.get("scale", 1),
                                "yoffset": old.get("yoffset", 0),
                                "xoffset": old.get("xoffset", 0),
                                "decimal": old.get("decimal", -7),
                                "value": old.get("value", 0),
                                "name": display_name,
                            }
                        )
                    if settings_ctx != rebuilt:
                        node["settings_ctx"] = rebuilt
                        touched = True

                for v in node.values():
                    _walk(v)
            elif isinstance(node, list):
                for v in node:
                    _walk(v)

        _walk(payload)
        if not touched:
            return

        try:
            context_cfg.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except Exception:
            return

    def _stage_stream_preset_to_context(
        self, preset_dir: Path, context_dir: Path, stream: str, target_port: int
    ) -> bool:
        # Copy required preset files into target context and patch stream-local runtime settings.
        for fname in ("vofa+.config.json", "vofa+.tabviews.json"):
            src = preset_dir / fname
            dst = context_dir / fname
            if not dst.exists() and src.exists():
                shutil.copy2(src, dst)

        context_cfg = context_dir / "vofa+.config.json"
        if context_cfg.exists():
            self._prepare_vofa_runtime(target_port, context_cfg)
            self._repair_stream_config_channel_names(stream, context_cfg)
        return True

    def _open_plot(self, workspace_rel: str, stream: str = "a") -> None:
        """Open VOFA for the given stream.

        Isolated stream approach:
          1. Kill any running VOFA (single-instance app — only one can be open).
          2. Copy this stream's preset files (vofa+.config.json + vofa+.tabviews.json)
             into this stream's isolated runtime context under .vofa_runtime/.
          3. Patch the UDP port in the config.
          4. Launch VOFA with stream-specific LOCALAPPDATA/APPDATA.

        To save your current VOFA layout back to the preset, call
        _capture_vofa_stream_preset(stream) before closing VOFA.
        """
        vofa = self._ensure_vofa_executable()
        if vofa is None:
            self._show_vofa_path_dialog()
            return

        stream_key = "b" if stream.lower().strip() == "b" else "a"
        target_port = self._get_vofa_stream_port(stream)
        preset_dir = self._get_vofa_stream_preset_dir(stream)

        # Kill just the target stream's VOFA
        self._terminate_vofa_stream(stream)

        # Resolve this stream's isolated VOFA context directory.
        local_app_root = self._vofa_runtime_root / stream_key / "localappdata"
        context_dir = self._get_vofa_context_dir(local_app_root)
        if context_dir is None:
            return

        # Stage into isolated context first.
        if not self._stage_stream_preset_to_context(preset_dir, context_dir, stream, target_port):
            return

        # Do NOT stage into system context to avoid cross-contamination.

        runtime_appdata = self._vofa_runtime_root / stream_key / "appdata"
        try:
            runtime_appdata.mkdir(parents=True, exist_ok=True)
        except Exception:
            return

        launch_env = os.environ.copy()
        launch_env["LOCALAPPDATA"] = str(local_app_root)
        launch_env["APPDATA"] = str(runtime_appdata)
        launch_env["USERPROFILE"] = str(local_app_root.parent)
        launch_env["TEMP"] = str(runtime_appdata / "Temp")
        launch_env["TMP"] = str(runtime_appdata / "Temp")

        try:
            proc = subprocess.Popen([vofa], cwd=str(self.repo_root), env=launch_env)
            self._vofa_procs[stream_key] = proc
        except FileNotFoundError:
            self._show_vofa_path_dialog()
        except Exception:
            return

    def _capture_vofa_stream_preset(self, stream: str) -> None:
        """Copy this stream's VOFA runtime context back into its preset dir.

        Call this after you've configured VOFA (renamed channels, organized tabs) and
        closed VOFA normally so it has written its state to disk.
        """
        stream_key = "b" if stream.lower().strip() == "b" else "a"
        preset_dir = self._get_vofa_stream_preset_dir(stream)
        preset_dir.mkdir(parents=True, exist_ok=True)

        local_app_root = self._vofa_runtime_root / stream_key / "localappdata"
        context_dir = self._get_vofa_context_dir(local_app_root)
        if context_dir is None:
            return

        # Hard lock: never capture from system %LOCALAPPDATA% context.
        cfg_p = context_dir / "vofa+.config.json"
        tab_p = context_dir / "vofa+.tabviews.json"
        if not (cfg_p.exists() and tab_p.exists()):
            return

        for fname in ("vofa+.config.json", "vofa+.tabviews.json"):
            src = context_dir / fname
            dst = preset_dir / fname
            if src.exists():
                shutil.copy2(src, dst)

        preset_cfg = preset_dir / "vofa+.config.json"
        self._repair_stream_config_channel_names(stream, preset_cfg)

    def _show_vofa_path_dialog(self) -> None:
        dpg.configure_item("vofa_path_modal", show=True)

        # Prefill input with current best guess.
        vofa = self._ensure_vofa_executable()
        if vofa is not None:
            dpg.set_value("vofa_path_input", vofa)

    def _browse_vofa_executable(self) -> None:
        # Uses tkinter file picker to locate the vofa+ executable.
        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            path = filedialog.askopenfilename(
                title="Select VOFA+ executable",
                initialdir="C:\\Program Files",
                filetypes=[("Executables", "*.exe"), ("All files", "*.*")],
            )
            if not path:
                return
            dpg.set_value("vofa_path_input", path)
        except Exception:
            return

    def _save_vofa_path(self) -> None:
        path = dpg.get_value("vofa_path_input")
        if not path:
            return
        path_str = str(path).strip()
        if not path_str or not Path(path_str).exists():
            return
        self._persist_vofa_executable(path_str)
        dpg.configure_item("vofa_path_modal", show=False)

    def _stop_button(self) -> None:
        self._emergency_stop()

    def _sdk_button(self) -> None:
        self._debouncer.call("flymode_sdk", self._send_cmd, 0x04, 1, 0.0)

    def _on_vrc_slider(self, sender: Any, app_data: Any, user_data: Any) -> None:
        idx = int(user_data)
        self._debouncer.call(f"vrc:{idx}", self._send_cmd, 0x06, idx, float(app_data))

    def _on_sdk_arm_request(self) -> None:
        self._send_cmd(0x0E, 0, 1.0)

    def _on_sdk_arm_clear(self) -> None:
        self._send_cmd(0x0E, 0, 0.0)

    def _on_bench_toggle(self, sender: Any, app_data: Any, user_data: Any) -> None:
        self._bench_mode_ui = bool(app_data)
        self._send_cmd(0x07, 0, 1.0 if self._bench_mode_ui else 0.0)
        try:
            mx = float(BENCH_THR_MAX if self._bench_mode_ui else RC_THR_MAX)
            dpg.configure_item("vrc_thr_slider", max_value=mx)
            t = float(dpg.get_value("vrc_thr_slider"))
            if t > mx:
                dpg.set_value("vrc_thr_slider", mx)
        except Exception:
            pass
        try:
            dpg.configure_item("vrc_bench_banner", show=self._bench_mode_ui)
        except Exception:
            pass

    def _build_virtual_rc_tab(self) -> None:
        dpg.add_text(
            "CONTROL SOURCE",
            color=(200, 200, 200, 255),
        )
        dpg.add_text("RC ACTIVE", tag="vrc_source_text", color=(0, 200, 0, 255))
        dpg.add_separator()

        dpg.add_checkbox(
            label="Bench test mode (throttle capped)",
            tag="vrc_bench_cb",
            default_value=False,
            callback=self._on_bench_toggle,
        )
        dpg.add_text(
            "BENCH MODE: Throttle capped at 20%",
            tag="vrc_bench_banner",
            show=False,
            color=(220, 180, 0, 255),
        )
        dpg.add_separator()

        with dpg.group(horizontal=True):
            dpg.add_button(
                label="SDK MODE",
                tag="vrc_sdk_btn",
                width=110,
                enabled=False,
                callback=lambda: self._send_cmd(0x04, 1, 0.0),
            )
            dpg.add_button(
                label="Virtual RC mode",
                width=135,
                callback=lambda: self._send_cmd(0x0D, 0, 1.0),
            )
            dpg.add_button(
                label="Paths (TWC) mode",
                width=135,
                callback=lambda: self._paths_cmd_twc(),
            )
        
        dpg.add_text("SDK arm request (GS_KeySDKflag)", color=(180, 180, 180, 255))
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="SDK ARM REQ",
                tag="vrc_arm_req_btn",
                width=160,
                callback=lambda: self._on_sdk_arm_request(),
            )
            dpg.add_button(
                label="ARM REQ OFF",
                tag="vrc_arm_off_btn",
                width=160,
                callback=lambda: self._on_sdk_arm_clear(),
            )
        dpg.add_separator()

        self.vrc_slider_tags = [
            dpg.add_slider_float(
                label="Throttle (PWM)",
                tag="vrc_thr_slider",
                min_value=float(RC_THR_MIN),
                max_value=float(RC_THR_MAX),
                default_value=float(RC_STICK_MID),
                width=400,
                callback=self._on_vrc_slider,
                user_data=0,
            ),
            dpg.add_slider_float(
                label="Pitch (PWM)",
                tag="vrc_pit_slider",
                min_value=float(RC_STICK_MIN),
                max_value=float(RC_STICK_MAX),
                default_value=float(RC_STICK_MID),
                width=400,
                callback=self._on_vrc_slider,
                user_data=1,
            ),
            dpg.add_slider_float(
                label="Roll (PWM)",
                tag="vrc_rol_slider",
                min_value=float(RC_STICK_MIN),
                max_value=float(RC_STICK_MAX),
                default_value=float(RC_STICK_MID),
                width=400,
                callback=self._on_vrc_slider,
                user_data=2,
            ),
            dpg.add_slider_float(
                label="Yaw (PWM)",
                tag="vrc_yaw_slider",
                min_value=float(RC_STICK_MIN),
                max_value=float(RC_STICK_MAX),
                default_value=float(RC_STICK_MID),
                width=400,
                callback=self._on_vrc_slider,
                user_data=3,
            ),
        ]

    def _build_monitor_tab(self) -> None:
        with dpg.group(horizontal=True):
            with dpg.child_window(width=600, height=-1, border=True):
                dpg.add_text("MRAC tracking", color=(200, 200, 200, 255))
                for ax in ["pitch", "roll", "yaw", "z"]:
                    dpg.add_text(f"{ax.upper()}  e")
                    dpg.add_progress_bar(tag=f"mon_bar_e_{ax}", default_value=0.0, width=-1)
                    dpg.add_text(f"{ax.upper()}  u_ad")
                    dpg.add_progress_bar(tag=f"mon_bar_u_{ax}", default_value=0.0, width=-1)
            with dpg.child_window(width=-1, height=-1, border=True):
                dpg.add_text("PID (FB / Des / U)", color=(200, 200, 200, 255))
                self._mon_pid_loops = [
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
                for lp in self._mon_pid_loops:
                    dpg.add_text("", tag=f"mon_pid_{lp}")
        dpg.add_separator()
        dpg.add_text("", tag="mon_footer")

    def _update_monitor_ui(self, a: Dict[str, float], b: Dict[str, float]) -> None:
        def col_for_e(abs_e: float) -> Tuple[int, int, int, int]:
            if abs_e < 0.1:
                return (0, 200, 0, 255)
            if abs_e < 0.3:
                return (220, 200, 0, 255)
            return (220, 40, 40, 255)

        for ax, ek, uk in [
            ("pitch", "mrac.pitch.e", "mrac.pitch.u_ad"),
            ("roll", "mrac.roll.e", "mrac.roll.u_ad"),
            ("yaw", "mrac.yaw.e", "mrac.yaw.u_ad"),
            ("z", "mrac.z.e", "mrac.z.u_ad"),
        ]:
            ev = abs(float(a.get(ek, 0.0)))
            uv = abs(float(a.get(uk, 0.0)))
            try:
                dpg.set_value(f"mon_bar_e_{ax}", min(1.0, ev / 0.5))
                dpg.configure_item(f"mon_bar_e_{ax}", overlay=f"{float(a.get(ek,0)):+.4f}")
                dpg.set_value(f"mon_bar_u_{ax}", min(1.0, uv / 2.0))
                dpg.configure_item(f"mon_bar_u_{ax}", overlay=f"{float(a.get(uk,0)):+.4f}")
                dpg.configure_item(f"mon_bar_e_{ax}", color=col_for_e(ev))
            except Exception:
                pass
        for lp in getattr(self, "_mon_pid_loops", []):
            fb = float(b.get(f"pid.{lp}.FB", 0.0))
            des = float(b.get(f"pid.{lp}.Des", 0.0))
            uu = float(b.get(f"pid.{lp}.U", 0.0))
            try:
                dpg.set_value(f"mon_pid_{lp}", f"{lp:8s}  FB={fb:10.4g}  Des={des:10.4g}  U={uu:10.4g}")
            except Exception:
                pass

    def _build_paths_tab(self) -> None:
        dpg.add_text(
            "Paths send firmware CMDs only (0x0A/0x0B/0x0C). Requires FlyMode SDK (Virtual RC tab).",
            color=(170, 170, 180, 255),
            wrap=900,
        )
        dpg.add_separator()
        with dpg.group(horizontal=True):
            with dpg.child_window(width=420, height=-1, border=True):
                dpg.add_text("Position source", color=(200, 200, 200, 255))
                dpg.add_combo(
                    tag="combo_pos_source",
                    items=["None", "Optical Flow", "Simulation"],
                    default_value="None",
                    width=280,
                    callback=lambda s, a: self._paths_refresh_ui(),
                )
                with dpg.group(horizontal=True):
                    b_slam = dpg.add_button(label="SLAM", enabled=False, width=80)
                    b_gps = dpg.add_button(label="GPS", enabled=False, width=80)
                with dpg.tooltip(parent=b_slam):
                    dpg.add_text("Coming soon")
                with dpg.tooltip(parent=b_gps):
                    dpg.add_text("Coming soon")
                dpg.add_separator()
                dpg.add_text("TWC target (m, deg)", color=(200, 200, 200, 255))
                dpg.add_input_float(tag="twc_tx", label="target x", width=200, default_value=0.0)
                dpg.add_input_float(tag="twc_ty", label="target y", width=200, default_value=0.0)
                dpg.add_input_float(tag="twc_tz", label="target z", width=200, default_value=0.0)
                dpg.add_input_float(tag="twc_yaw", label="yaw deg", width=200, default_value=0.0)
                dpg.add_button(
                    label="Execute TWC",
                    tag="btn_path_twc_exec",
                    width=200,
                    enabled=False,
                    callback=lambda: self._paths_cmd_twc(),
                )
                dpg.add_text("Distance: -- m", tag="txt_path_twc_dist", color=(210, 210, 210, 255))
                dpg.add_button(
                    label="Abort Path (Return to V-RC)",
                    width=200,
                    callback=lambda: self._send_cmd(0x0D, 0, 1.0),
                )
                dpg.add_separator()
                dpg.add_text("Sinusoid (center m, axis 0=X 1=Y 2=Z)", color=(200, 200, 200, 255))
                dpg.add_input_float(tag="sin_cx", label="cx", width=120, default_value=0.0)
                dpg.add_input_float(tag="sin_cy", label="cy", width=120, default_value=0.0)
                dpg.add_input_float(tag="sin_cz", label="cz", width=120, default_value=0.0)
                dpg.add_input_float(tag="sin_amp", label="amplitude m", width=160, default_value=0.5)
                dpg.add_input_float(tag="sin_freq", label="freq Hz", width=120, default_value=0.2)
                dpg.add_input_float(tag="sin_dur", label="duration s", width=120, default_value=30.0)
                dpg.add_input_float(tag="sin_axis", label="axis", width=120, default_value=0.0, min_value=0.0, max_value=2.0)
                dpg.add_button(
                    label="Execute sinusoid",
                    tag="btn_path_sin_exec",
                    width=200,
                    enabled=False,
                    callback=lambda: self._paths_cmd_sinusoid(),
                )
                dpg.add_separator()
                dpg.add_text("Circle (XY plane)", color=(200, 200, 200, 255))
                dpg.add_input_float(tag="cir_cx", label="cx", width=120, default_value=0.0)
                dpg.add_input_float(tag="cir_cy", label="cy", width=120, default_value=0.0)
                dpg.add_input_float(tag="cir_cz", label="cz", width=120, default_value=0.0)
                dpg.add_input_float(tag="cir_r", label="radius m", width=120, default_value=1.0)
                dpg.add_input_float(tag="cir_omega", label="omega rad/s", width=140, default_value=0.3)
                dpg.add_input_float(tag="cir_dur", label="duration s", width=120, default_value=60.0)
                dpg.add_button(
                    label="Execute circle",
                    tag="btn_path_circ_exec",
                    width=200,
                    enabled=False,
                    callback=lambda: self._paths_cmd_circle(),
                )
            with dpg.child_window(width=-1, height=-1, border=True):
                dpg.add_text("2D preview (XY, 1 px = 0.01 m) @ 10 Hz", color=(200, 200, 200, 255))
                dpg.add_drawlist(tag="paths_drawlist", width=400, height=400)
                dpg.add_button(label="Clear Trace", callback=lambda: self._paths_clear_trace())

    def _build_safety_tab(self) -> None:
        dpg.add_checkbox(
            tag="cb_expert_mode",
            label="Expert mode (unlocks overrides)",
            default_value=False,
            callback=lambda s, a: self._on_expert_toggle(a),
        )
        dpg.add_text(
            "EXPERT MODE: Safety limits relaxed. Ensure props are removed or area is clear.",
            tag="txt_expert_warn",
            show=False,
            color=(220, 60, 60, 255),
        )
        dpg.add_separator()
        with dpg.group(tag="safety_expert_controls", show=False):
            dpg.add_slider_float(
                tag="sf_vhoriz",
                label="Max horiz speed (m/s)",
                min_value=0.1,
                max_value=5.0,
                default_value=1.0,
                callback=lambda s, a: self._send_cmd(0x09, 0, float(a)),
                width=400,
            )
            dpg.add_slider_float(
                tag="sf_vvert",
                label="Max vert speed (m/s)",
                min_value=0.1,
                max_value=3.0,
                default_value=1.0,
                callback=lambda s, a: self._send_cmd(0x09, 1, float(a)),
                width=400,
            )
            dpg.add_slider_float(
                tag="sf_pmax",
                label="Max pitch (deg)",
                min_value=5.0,
                max_value=45.0,
                default_value=15.0,
                callback=lambda s, a: self._send_cmd(0x09, 2, float(a)),
                width=400,
            )
            dpg.add_slider_float(
                tag="sf_rmax",
                label="Max roll (deg)",
                min_value=5.0,
                max_value=45.0,
                default_value=15.0,
                callback=lambda s, a: self._send_cmd(0x09, 3, float(a)),
                width=400,
            )
            dpg.add_separator()
            dpg.add_text("MRAC authority / mixer (moved from MRAC tab)", color=(180, 180, 180, 255))
            for ax in ["pitch", "roll", "yaw", "z"]:
                self._build_mixer_blocks(ax)
        dpg.add_separator()
        dpg.add_text("Preset safety profiles", color=(200, 200, 200, 255))
        dpg.add_button(label="Indoor Careful", callback=lambda: self._apply_safety_profile("indoor"))
        dpg.add_button(label="Outdoor Normal", callback=lambda: self._apply_safety_profile("outdoor"))
        dpg.add_button(label="Research Mode", callback=lambda: self._apply_safety_profile("research"))
        self._on_expert_toggle(False)

    def _on_expert_toggle(self, val: bool) -> None:
        self._expert_mode = bool(val)
        try:
            dpg.configure_item("txt_expert_warn", show=self._expert_mode)
            dpg.configure_item("safety_expert_controls", show=self._expert_mode)
        except Exception:
            pass

    def _apply_safety_profile(self, name: str) -> None:
        p = self.repo_root / "config" / "safety_profiles.json"
        if not p.exists():
            return
        try:
            cfg_all = json.loads(p.read_text(encoding="utf-8"))
            cfg = cfg_all.get(name, {})
        except Exception:
            return
        if not cfg:
            return
        if not self._expert_mode and name == "research":
            return
        self._send_cmd(0x09, 0, float(cfg.get("max_horizontal_speed_mps", 1.0)))
        self._send_cmd(0x09, 1, float(cfg.get("max_vertical_speed_mps", 1.0)))
        self._send_cmd(0x09, 2, float(cfg.get("max_pitch_deg", 15.0)))
        self._send_cmd(0x09, 3, float(cfg.get("max_roll_deg", 15.0)))

    def _build_flight_log_tab(self) -> None:
        logs = self.repo_root / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        dpg.add_text("Diagnosis & Disturbance Recording (Auto-Analysis)", color=(180, 220, 255, 255))
        dpg.add_text("Automatically plots and saves diagnostics when recording stops.", color=(160, 160, 160, 255))
        
        with dpg.group(horizontal=True):
            dpg.add_input_float(label="Duration (s) [0 = continuous]", tag="inp_diag_dur", default_value=0.0, width=120)
        
        with dpg.group(horizontal=True):
            dpg.add_button(label="Start Recording", tag="btn_diag_start", callback=self._start_diag_recording)
            dpg.add_button(label="Stop & Analyze Now", tag="btn_diag_stop", callback=self._stop_diag_recording)
        dpg.add_text("Ready.", tag="txt_diag_status", color=(100, 255, 100, 255))
        
        dpg.add_separator()
        dpg.add_text("Flight recording (20 Hz merged telemetry → CSV)", color=(200, 200, 200, 255))
        dpg.add_button(label="Start recording", tag="btn_log_start", callback=self._flight_log_start)
        dpg.add_button(label="Stop", tag="btn_log_stop", callback=self._flight_log_stop)
        dpg.add_text("", tag="txt_log_status")
        dpg.add_separator()
        dpg.add_text("Path memory (loc Des)", color=(200, 200, 200, 255))
        dpg.add_button(label="Record path", callback=self._path_mem_start)
        dpg.add_button(label="Stop path", callback=self._path_mem_stop)
        dpg.add_listbox(tag="list_log_files", items=[], width=400, num_items=6)

    def _start_diag_recording(self) -> None:
        if not self.connected:
            dpg.set_value("txt_diag_status", "Cannot start: Not connected to drone.")
            dpg.configure_item("txt_diag_status", color=(255, 100, 100, 255))
            return

        if self._recording_flight:
            dpg.set_value("txt_diag_status", "Recording already in progress.")
            dpg.configure_item("txt_diag_status", color=(255, 200, 50, 255))
            return
            
        try:
            dur = max(0.0, float(dpg.get_value("inp_diag_dur")))
        except Exception:
            dur = 0.0
        self._flight_log_start()
        
        if dur > 0:
            dpg.set_value("txt_diag_status", f"Recording for {dur}s...")
            dpg.configure_item("txt_diag_status", color=(255, 200, 50, 255))

            def stop_later():
                self._post_ui_call(self._stop_diag_recording)

            threading.Timer(dur, stop_later).start()
        else:
            dpg.set_value("txt_diag_status", "Recording continuous. Press Stop & Analyze.")
            dpg.configure_item("txt_diag_status", color=(255, 200, 50, 255))
            
    def _stop_diag_recording(self) -> None:
        if not self._recording_flight:
            return
            
        # Get path before stopping
        active_log = self._flight_logger._path
        self._flight_log_stop()
        dpg.set_value("txt_diag_status", "Recording stopped. Analyzing data...")
        dpg.configure_item("txt_diag_status", color=(50, 200, 255, 255))
        
        if active_log and active_log.exists():
            def run_analysis():
                script_path = self.repo_root / "ground_station" / "scripts" / "analyze_flight_log.py"
                if not script_path.exists():
                    self._post_ui_call(dpg.set_value, "txt_diag_status", "Error: analyze_flight_log.py script missing.")
                    self._post_ui_call(dpg.configure_item, "txt_diag_status", color=(255, 50, 50, 255))
                    return
                    
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"
                out = subprocess.run(
                    [sys.executable, str(script_path), str(active_log)],
                    capture_output=True, text=True, env=env
                )
                
                try:
                    if out.returncode == 0:
                        lines = out.stdout.splitlines()
                        saved_path = "Analysis_plots/"
                        for line in lines:
                            if line.strip().startswith("Saving plots to:") or line.strip().startswith(str(self.repo_root)):
                                saved_path = line.strip().split("Saving plots to:")[-1].strip()

                        self._post_ui_call(dpg.set_value, "txt_diag_status", "Success! Plots saved.")
                        self._post_ui_call(dpg.configure_item, "txt_diag_status", color=(50, 255, 50, 255))
                        self._post_ui_call(
                            dpg.set_value,
                            "diag_result_text",
                            f"Detailed analysis successful!\n\nSource CSV: {active_log.name}\nPlots Location:\n{saved_path}",
                        )
                        self._post_ui_call(dpg.configure_item, "diag_result_modal", show=True)

                        # --- Chain deep analysis ---
                        deep_script = self.repo_root / "ground_station" / "scripts" / "deep_analysis.py"
                        if deep_script.exists():
                            self._post_ui_call(dpg.set_value, "txt_diag_status",
                                               "Plots done. Running deep analysis...")
                            self._post_ui_call(dpg.configure_item, "txt_diag_status",
                                               color=(50, 200, 255, 255))
                            deep_out = subprocess.run(
                                [sys.executable, str(deep_script), str(active_log), saved_path],
                                capture_output=True, text=True, env=env
                            )
                            if deep_out.returncode == 0:
                                self._post_ui_call(dpg.set_value, "txt_diag_status",
                                                   "Plots + Deep Analysis complete!")
                                self._post_ui_call(dpg.configure_item, "txt_diag_status",
                                                   color=(50, 255, 50, 255))
                                # Update modal text to include JSON path
                                json_path = self.repo_root / "ground_station" / "results" / f"{active_log.stem}.json"
                                self._post_ui_call(
                                    dpg.set_value, "diag_result_text",
                                    f"Analysis complete!\n\n"
                                    f"Source CSV: {active_log.name}\n"
                                    f"Plots + Report: {saved_path}\n"
                                    f"JSON Record: {json_path}",
                                )
                            else:
                                self._post_ui_call(dpg.set_value, "txt_diag_status",
                                                   "Plots OK. Deep analysis had errors (check console).")
                                self._post_ui_call(dpg.configure_item, "txt_diag_status",
                                                   color=(255, 200, 50, 255))
                                print(f"[deep_analysis] stderr:\n{deep_out.stderr}")
                                print(f"[deep_analysis] stdout:\n{deep_out.stdout}")
                    else:
                        self._post_ui_call(dpg.set_value, "txt_diag_status", "Analysis failed. Check console.")
                        self._post_ui_call(dpg.configure_item, "txt_diag_status", color=(255, 50, 50, 255))
                        print("Analysis output:", out.stderr, out.stdout)
                except Exception:
                    pass
                    
            threading.Thread(target=run_analysis, daemon=True).start()
        else:
            dpg.set_value("txt_diag_status", "Error: Log file not found.")
            dpg.configure_item("txt_diag_status", color=(255, 100, 100, 255))

    def _flight_log_start(self) -> None:
        # Logging should work for both local serial bridge and remote UDP bridge modes.
        if not self.connected:
            return
        logs = self.repo_root / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        fn = logs / f"flight_{int(time.time())}.csv"
        self._flight_logger.start(fn)
        self._recording_flight = True

    def _flight_log_stop(self) -> None:
        self._flight_logger.stop()
        self._recording_flight = False

    def _path_mem_start(self) -> None:
        self._recording_path = True
        self._path_point_buffer.clear()

    def _path_mem_stop(self) -> None:
        self._recording_path = False
        logs = self.repo_root / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        p = logs / f"path_{int(time.time())}.csv"
        try:
            with open(p, "w", encoding="utf-8") as f:
                f.write("locx_Des,locy_Des\n")
                for row in self._path_point_buffer:
                    f.write(f"{row[0]},{row[1]}\n")
        except Exception:
            pass

    def _build_gui(self) -> None:
        dpg.create_context()

        with dpg.theme(tag="theme_emergency_stop"):
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button, (200, 45, 45, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (230, 70, 70, 255))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (160, 30, 30, 255))
                dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 255, 255, 255))

        with dpg.theme(tag="theme_mode_sdk"):
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button, (60, 60, 60, 255), tag="color_mode_sdk_btn")

        with dpg.theme(tag="theme_mode_stop"):
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button, (60, 60, 60, 255), tag="color_mode_stop_btn")

        cfg = _simple_yaml_kv_load(self.config_path)
        default_port = str(cfg.get("serial_port", "COM3"))
        default_baud = int(cfg.get("baud_rate", 115200))

        # Serial port dropdown options.
        ports, port_err = self._detect_serial_ports(fallback=default_port)

        with dpg.window(
            label="UAV Dashboard",
            width=1400,
            height=860,
            tag="main_window",
            no_collapse=True,
        ):
            with dpg.handler_registry(tag="hk_global_space"):
                # Dear PyGui key enums differ across versions.
                space_key = getattr(dpg, "mvKey_Space", None)
                if space_key is None:
                    space_key = getattr(dpg, "mvKey_Spacebar", None)
                if space_key is not None:
                    dpg.add_key_press_handler(space_key, callback=lambda s, a: self._emergency_stop())

            with dpg.group(horizontal=True):
                # Fixed-width sidebar: connection, status, E-STOP, VOFA shortcuts.
                with dpg.child_window(width=200, height=-1, border=True):
                    dpg.add_text("Connection", color=(200, 200, 200, 255))
                    dpg.add_combo(
                        items=ports,
                        default_value=default_port if default_port in ports else ports[0],
                        tag="com_selector",
                        width=-1,
                    )
                    dpg.add_input_text(
                        tag="com_manual_input",
                        hint="Manual COM (e.g. COM7)",
                        width=-1,
                    )
                    dpg.add_button(label="Refresh Ports", width=-1, callback=lambda: self._refresh_com_ports())
                    dpg.add_text("Baud")
                    dpg.add_combo(
                        items=["115200", "57600", "38400", "19200", "9600"],
                        default_value=str(default_baud),
                        tag="baud_selector",
                        width=-1,
                    )
                    dpg.add_button(
                        label="Disconnect" if self.connected else "Connect",
                        tag="conn_button",
                        width=-1,
                        callback=lambda: self._on_connect_disconnect(),
                    )
                    dpg.add_text(
                        port_err if port_err else f"Detected {len(ports)} port(s)",
                        tag="conn_detail_text",
                        color=(220, 70, 70, 255) if port_err else (170, 190, 220, 255),
                        wrap=180,
                    )
                    dpg.add_separator()
                    dpg.add_text("Status", color=(200, 200, 200, 255))
                    self.arm_value_tag = dpg.add_text("ARM: ?", color=(220, 0, 0, 255))
                    dpg.add_text("FlyMode: ?", tag="status_fly_sidebar", color=(180, 180, 180, 255))
                    dpg.add_text("SBUS: ?", tag="status_sbus_sidebar", color=(180, 180, 180, 255))
                    dpg.add_text("Bench: OFF", tag="status_bench_sidebar", color=(180, 180, 180, 255))
                    dpg.add_separator()
                    
                    dpg.add_text("Flight Mode", color=(200, 200, 200, 255))
                    dpg.add_button(
                        label="SDK Mode",
                        tag="btn_mode_sdk",
                        width=-1,
                        callback=lambda: self._send_cmd(0x04, 1, 1.0)
                    )
                    dpg.bind_item_theme("btn_mode_sdk", "theme_mode_sdk")
                    dpg.add_button(
                        label="Dangerous Stop",
                        tag="btn_mode_stop",
                        width=-1,
                        callback=lambda: self._send_cmd(0x04, 0, 0.0)
                    )
                    dpg.bind_item_theme("btn_mode_stop", "theme_mode_stop")
                    dpg.add_separator()
                    
                    dpg.add_button(
                        label="STOP",
                        tag="stop_button",
                        width=-1,
                        height=42,
                        callback=lambda: self._stop_button(),
                    )
                    dpg.bind_item_theme("stop_button", "theme_emergency_stop")
                    dpg.add_separator()
                    dpg.add_text("VOFA+", color=(200, 200, 200, 255))
                    dpg.add_button(
                        label="Frame A Workspace",
                        width=-1,
                        callback=lambda: self._open_plot("presets/vofa/full.tabviews.json", stream="a"),
                    )
                    dpg.add_button(
                        label="Frame B Workspace",
                        width=-1,
                        callback=lambda: self._open_plot("presets/vofa/mrac_errors.tabviews.json", stream="b"),
                    )

                with dpg.child_window(width=-1, height=-1, border=False):
                    with dpg.group(horizontal=False):
                        with dpg.tab_bar():
                            with dpg.tab(label="Monitor", tag="tab_monitor"):
                                self._build_monitor_tab()
                            with dpg.tab(label="Virtual RC", tag="tab_vrc"):
                                self._build_virtual_rc_tab()
                            with dpg.tab(label="PID Tuning", tag="tab_pid"):
                                with dpg.tab_bar():
                                    with dpg.tab(label="Pitch"):
                                        self._build_pid_axis_tab("pitch")
                                    with dpg.tab(label="Roll"):
                                        self._build_pid_axis_tab("roll")
                                    with dpg.tab(label="Yaw"):
                                        self._build_pid_axis_tab("yaw")
                                    with dpg.tab(label="Z"):
                                        self._build_pid_axis_tab("z")
                            with dpg.tab(label="MRAC Tuning", tag="tab_mrac"):
                                with dpg.tab_bar():
                                    with dpg.tab(label="Pitch"):
                                        self._build_mrac_axis_tab("pitch")
                                    with dpg.tab(label="Roll"):
                                        self._build_mrac_axis_tab("roll")
                                    with dpg.tab(label="Yaw"):
                                        self._build_mrac_axis_tab("yaw")
                                    with dpg.tab(label="Z"):
                                        self._build_mrac_axis_tab("z")
                            with dpg.tab(label="Paths", tag="tab_paths"):
                                self._build_paths_tab()
                            with dpg.tab(label="Safety", tag="tab_safety"):
                                self._build_safety_tab()
                            with dpg.tab(label="Flight Log", tag="tab_flog"):
                                self._build_flight_log_tab()
                        dpg.add_separator()
                        with dpg.group(horizontal=True):
                            dpg.add_text("Load preset:")
                            dpg.add_combo(
                                tag="combo_preset_pick",
                                items=["(loading)"],
                                width=220,
                                callback=self._on_pick_preset,
                            )
                            dpg.add_button(
                                label="Browse…",
                                callback=lambda: self._browse_and_load_preset(),
                            )
                            dpg.add_button(
                                label="Save Preset",
                                callback=lambda: dpg.configure_item("save_preset_modal", show=True),
                            )
                            dpg.add_text("—", tag="txt_preset_name", color=(160, 200, 255, 255))

        # Modals.
        with dpg.window(
            label="Analysis Complete",
            modal=True,
            show=False,
            width=540,
            height=250,
            pos=(300, 200),
            tag="diag_result_modal",
        ):
            dpg.add_text("", tag="diag_result_text", wrap=500)
            dpg.add_button(
                label="OK",
                width=100,
                pos=(420, 200),
                callback=lambda: dpg.configure_item("diag_result_modal", show=False),
            )

        with dpg.window(
            label="Connection Status",
            modal=True,
            show=False,
            width=540,
            height=170,
            pos=(430, 260),
            tag="conn_result_modal",
        ):
            dpg.add_text("", tag="conn_result_text", wrap=500)
            dpg.add_button(
                label="OK",
                width=100,
                pos=(420, 120),
                callback=lambda: dpg.configure_item("conn_result_modal", show=False),
            )

        with dpg.window(
            label="Save Preset",
            modal=True,
            show=False,
            no_title_bar=False,
            width=360,
            height=160,
            pos=(500, 300),
            tag="save_preset_modal",
        ):
            dpg.add_text("Preset name:")
            dpg.add_input_text(tag="preset_name_input", default_value="default")
            dpg.add_button(
                label="Save",
                pos=(160, 90),
                width=80,
                callback=lambda: self._save_preset_modal_cb(),
            )
            dpg.add_button(
                label="Cancel",
                pos=(250, 90),
                width=80,
                callback=lambda: dpg.configure_item("save_preset_modal", show=False),
            )

        with dpg.window(
            label="VOFA+ Executable",
            modal=True,
            show=False,
            width=520,
            height=170,
            pos=(450, 300),
            tag="vofa_path_modal",
        ):
            dpg.add_text("VOFA+ executable path:")
            dpg.add_input_text(tag="vofa_path_input", width=360)
            dpg.add_button(
                label="Browse...",
                pos=(380, 40),
                width=100,
                height=30,
                callback=lambda: self._browse_vofa_executable(),
            )
            dpg.add_button(
                label="Save",
                pos=(250, 110),
                width=100,
                callback=lambda: self._save_vofa_path(),
            )
            dpg.add_button(
                label="Cancel",
                pos=(360, 110),
                width=100,
                callback=lambda: dpg.configure_item("vofa_path_modal", show=False),
            )

    def _save_preset_modal_cb(self) -> None:
        name = str(dpg.get_value("preset_name_input") or "").strip()
        if not name:
            return
        self._save_preset_to_name(name)
        dpg.configure_item("save_preset_modal", show=False)

    def _build_pid_blocks(self, axis: str) -> None:
        default_outer = {"Kp": 5.0, "Ki": 0.5, "Kd": 2.5}
        default_inner = {"Kp": 10.0, "Ki": 0.25, "Kd": 1.0}
        if axis == "z":
            dpg.add_text(
                "Z-axis uses single-loop rate control.",
                color=(160, 160, 160, 255),
            )
            dpg.add_separator()
            dpg.add_text("Z Rate PID")
            with dpg.group(horizontal=False):
                self.inner_pid[axis] = {
                    "Kp": dpg.add_slider_float(
                        label="Kp",
                        min_value=0.0,
                        max_value=20.0,
                        default_value=default_inner["Kp"],
                        callback=self._on_z_rate_pid_slider,
                        user_data="Kp",
                        width=350,
                    ),
                    "Ki": dpg.add_slider_float(
                        label="Ki",
                        min_value=0.0,
                        max_value=0.5,
                        default_value=default_inner["Ki"],
                        callback=self._on_z_rate_pid_slider,
                        user_data="Ki",
                        width=350,
                    ),
                    "Kd": dpg.add_slider_float(
                        label="Kd",
                        min_value=0.0,
                        max_value=2.0,
                        default_value=default_inner["Kd"],
                        callback=self._on_z_rate_pid_slider,
                        user_data="Kd",
                        width=350,
                    ),
                }
            dpg.add_separator()
        else:
            self.outer_pid[axis] = {}
            self.inner_pid[axis] = {}
            dpg.add_text(f"{axis.upper()} - Outer Loop PID (Angle)")
            with dpg.group(horizontal=False):
                self.outer_pid[axis]["Kp"] = dpg.add_slider_float(
                    label="Kp",
                    min_value=0.0,
                    max_value=10.0,
                    default_value=default_outer["Kp"],
                    callback=self._on_outer_pid_slider,
                    user_data=(axis, "Kp"),
                    width=350,
                )
                self.outer_pid[axis]["Ki"] = dpg.add_slider_float(
                    label="Ki",
                    min_value=0.0,
                    max_value=1.0,
                    default_value=default_outer["Ki"],
                    callback=self._on_outer_pid_slider,
                    user_data=(axis, "Ki"),
                    width=350,
                )
                self.outer_pid[axis]["Kd"] = dpg.add_slider_float(
                    label="Kd",
                    min_value=0.0,
                    max_value=5.0,
                    default_value=default_outer["Kd"],
                    callback=self._on_outer_pid_slider,
                    user_data=(axis, "Kd"),
                    width=350,
                )

            dpg.add_separator()

            dpg.add_text(f"{axis.upper()} - Inner Loop PID (Rate)")
            with dpg.group(horizontal=False):
                self.inner_pid[axis]["Kp"] = dpg.add_slider_float(
                    label="Kp",
                    min_value=0.0,
                    max_value=20.0,
                    default_value=default_inner["Kp"],
                    callback=self._on_inner_pid_slider,
                    user_data=(axis, "Kp"),
                    width=350,
                )
                self.inner_pid[axis]["Ki"] = dpg.add_slider_float(
                    label="Ki",
                    min_value=0.0,
                    max_value=0.5,
                    default_value=default_inner["Ki"],
                    callback=self._on_inner_pid_slider,
                    user_data=(axis, "Ki"),
                    width=350,
                )
                self.inner_pid[axis]["Kd"] = dpg.add_slider_float(
                    label="Kd",
                    min_value=0.0,
                    max_value=2.0,
                    default_value=default_inner["Kd"],
                    callback=self._on_inner_pid_slider,
                    user_data=(axis, "Kd"),
                    width=350,
                )

            dpg.add_separator()

    def _build_mrac_blocks(self, axis: str) -> None:
        self.mrac_gamma[axis] = []
        self.mrac_what_limit[axis] = []
        self.mrac_what_tol[axis] = []
        dpg.add_text(f"{axis.upper()} - MRAC (gamma / What_limit / What_tol)")
        with dpg.group(horizontal=False):
            for i in range(8):
                gamma_tag = dpg.add_slider_float(
                    label=f"gamma[{i}]",
                    min_value=0.0,
                    max_value=10.0,
                    default_value=1.0,
                    callback=self._on_mrac_slider,
                    user_data=(axis, "gamma", i),
                    width=350,
                )
                limit_tag = dpg.add_slider_float(
                    label=f"What_limit[{i}]",
                    min_value=0.0,
                    max_value=10.0,
                    default_value=1.0,
                    callback=self._on_mrac_slider,
                    user_data=(axis, "What_limit", i),
                    width=350,
                )
                tol_tag = dpg.add_slider_float(
                    label=f"What_tol[{i}]",
                    min_value=0.0,
                    max_value=1.0,
                    default_value=0.1,
                    callback=self._on_mrac_slider,
                    user_data=(axis, "What_tol", i),
                    width=350,
                )
                self.mrac_gamma[axis].append(gamma_tag)
                self.mrac_what_limit[axis].append(limit_tag)
                self.mrac_what_tol[axis].append(tol_tag)
                self.mrac_slider_tags.append((axis, "gamma", i, gamma_tag))
                self.mrac_slider_tags.append((axis, "What_limit", i, limit_tag))
                self.mrac_slider_tags.append((axis, "What_tol", i, tol_tag))
        dpg.add_separator()

    def _build_mixer_blocks(self, axis: str) -> None:
        dpg.add_text(f"{axis.upper()} - Mixer / saturation")
        with dpg.group(horizontal=False):
            self.mixer_slider[axis] = dpg.add_slider_float(
                label="MRAC_TO_MIXER",
                min_value=0.0,
                max_value=1000.0,
                default_value=500.0,
                callback=self._on_mixer_slider,
                user_data=(axis, "MRAC_TO_MIXER"),
                width=350,
            )
            self.u_max_slider[axis] = dpg.add_slider_float(
                label="U_MAX",
                min_value=0.0,
                max_value=20.0,
                default_value=10.0,
                callback=self._on_mixer_slider,
                user_data=(axis, "U_MAX"),
                width=350,
            )

    def _build_pid_axis_tab(self, axis: str) -> None:
        self._build_pid_blocks(axis)

    def _build_mrac_axis_tab(self, axis: str) -> None:
        self._build_mrac_blocks(axis)

    def run(self) -> None:
        try:
            # First launch: show VOFA path dialog if executable missing.
            if not self._vofa_checked:
                self._vofa_checked = True
                if self._ensure_vofa_executable() is None:
                    dpg.configure_item("vofa_path_modal", show=True)

            dpg.create_viewport(title="UAV Dashboard", width=1400, height=860)
            dpg.setup_dearpygui()
            try:
                dpg.set_primary_window("main_window", True)
            except Exception:
                pass
            dpg.show_viewport()

            # Manual render loop so we can poll serial_bridge state on the main thread.
            while dpg.is_dearpygui_running():
                self._frame()
                dpg.render_dearpygui_frame()
        finally:
            self._telem_stop.set()
            self._stop_bridge()
            dpg.destroy_context()


def main() -> None:
    Dashboard().run()


if __name__ == "__main__":
    main()

