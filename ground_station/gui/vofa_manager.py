from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ground_station.gui._gui_utils import simple_yaml_kv_load


class VofaManager:
    """Owns all VOFA+ process, context, workspace, and preset management.

    Dashboard holds one instance and delegates via open_plot(), ensure_executable(),
    persist_executable(), and capture_stream_preset(). All subprocess/file logic lives here;
    DPG calls stay in Dashboard.
    """

    def __init__(
        self,
        repo_root: Path,
        config_path: Path,
        show_path_dialog_cb: Callable[[], None],
        get_max_num_basis_cb: Callable[[], int],
    ) -> None:
        self._repo_root = repo_root
        self._config_path = config_path
        self._show_path_dialog = show_path_dialog_cb
        self._get_max_num_basis = get_max_num_basis_cb
        self._runtime_root = repo_root / ".vofa_runtime"
        self._procs: Dict[str, Optional[subprocess.Popen]] = {"a": None, "b": None}
        self._executable: Optional[str] = None
        self.checked: bool = False  # True once run() has attempted discovery

    # ------------------------------------------------------------------
    # Public API (called from Dashboard)
    # ------------------------------------------------------------------

    def ensure_executable(self) -> Optional[str]:
        if self._executable and Path(self._executable).exists():
            return self._executable
        cfg = simple_yaml_kv_load(self._config_path)
        configured = cfg.get("vofa_executable")
        if isinstance(configured, str) and configured and Path(configured).exists():
            self._executable = configured
            return configured
        discovered = self._discover_install_path()
        if discovered:
            self.persist_executable(discovered)
            return discovered
        return None

    def persist_executable(self, path_str: str) -> None:
        self._executable = path_str
        try:
            cfg = simple_yaml_kv_load(self._config_path)
            if str(cfg.get("vofa_executable", "")).strip() == path_str:
                return
            cfg["vofa_executable"] = path_str
            from ground_station.gui._gui_utils import simple_yaml_kv_write
            simple_yaml_kv_write(self._config_path, cfg)
        except Exception:
            return

    def open_plot(self, workspace_rel: str, stream: str = "a") -> None:
        """Launch VOFA+ for the given stream with its isolated context."""
        vofa = self.ensure_executable()
        if vofa is None:
            self._show_path_dialog()
            return

        stream_key = "b" if stream.lower().strip() == "b" else "a"
        target_port = self._get_stream_port(stream)
        preset_dir = self._get_stream_preset_dir(stream)

        self._terminate_stream(stream)

        local_app_root = self._runtime_root / stream_key / "localappdata"
        context_dir = self._get_context_dir(local_app_root)
        if context_dir is None:
            return

        # On first use the isolated context is empty. Pull the user's existing system
        # VOFA+ config (with their named channels/layout) so nothing is lost.
        context_cfg = context_dir / "vofa+.config.json"
        if not context_cfg.exists():
            self._sync_system_context_to_stream_cache(stream)

        if not self._stage_stream_preset_to_context(preset_dir, context_dir, stream, target_port):
            return

        runtime_appdata = self._runtime_root / stream_key / "appdata"
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
            proc = subprocess.Popen([vofa], cwd=str(self._repo_root), env=launch_env)
            self._procs[stream_key] = proc
        except FileNotFoundError:
            self._show_path_dialog()
        except Exception:
            return

    def capture_stream_preset(self, stream: str) -> None:
        """Copy this stream's VOFA runtime context back into its preset dir."""
        stream_key = "b" if stream.lower().strip() == "b" else "a"
        preset_dir = self._get_stream_preset_dir(stream)
        preset_dir.mkdir(parents=True, exist_ok=True)

        local_app_root = self._runtime_root / stream_key / "localappdata"
        context_dir = self._get_context_dir(local_app_root)
        if context_dir is None:
            return

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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _discover_install_path(self) -> Optional[str]:
        exe_names = ["VOFA+.exe", "vofa+.exe", "VOFA.exe", "vofa.exe"]
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
        roots.extend([home, home / "Desktop", home / "Documents", home / "Downloads"])
        rel_dirs = [
            Path("VOFA+"),
            Path("VOFA"),
            Path("Programs") / "VOFA+",
            Path("Programs") / "VOFA",
        ]
        seen: set = set()
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

    def _resolve_workspace_path(self, workspace_rel: str) -> Path:
        p = (self._repo_root / workspace_rel).resolve()
        if p.exists():
            return p
        candidates: List[Path] = []
        if p.suffix.lower() == ".vofa":
            candidates.append(p.with_suffix(".tabviews.json"))
            candidates.append(p.with_suffix(".json"))
            candidates.append(p.with_name(p.name + ".tabviews.json"))
        for c in candidates:
            if c.exists():
                return c
        return p

    def _get_stream_port(self, stream: str) -> int:
        cfg = simple_yaml_kv_load(self._config_path)
        if stream.lower().strip() == "b":
            raw = cfg.get("vofa_port_b", cfg.get("vofa_port", 1348))
        else:
            raw = cfg.get("vofa_port_a", cfg.get("vofa_port", 1347))
        try:
            return int(raw)
        except Exception:
            return 1348 if stream.lower().strip() == "b" else 1347

    def _get_latest_context_file(
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

    def _get_context_config_path(self, local_app_override: Optional[Path] = None) -> Optional[Path]:
        return self._get_latest_context_file("vofa+.config.json", local_app_override)

    def _get_context_tabviews_path(self, local_app_override: Optional[Path] = None) -> Optional[Path]:
        return self._get_latest_context_file("vofa+.tabviews.json", local_app_override)

    def _get_context_dir(self, local_app_override: Optional[Path] = None) -> Optional[Path]:
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

        found_ports: set = set()

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

        port_a = self._get_stream_port("a")
        port_b = self._get_stream_port("b")
        has_a = port_a in found_ports
        has_b = port_b in found_ports
        if has_a and not has_b:
            return "a"
        if has_b and not has_a:
            return "b"
        return None

    def _sync_system_context_to_stream_cache(self, stream: str) -> None:
        stream_key = "b" if stream.lower().strip() == "b" else "a"
        cache_local_app = self._runtime_root / stream_key / "localappdata"
        cache_context = self._get_context_dir(cache_local_app)
        if cache_context is None:
            return
        system_cfg = self._get_context_config_path()
        system_tabviews = self._get_context_tabviews_path()
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
        source_context = self._get_context_dir(local_app_root)
        target_context = self._get_context_dir()
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

    def _ensure_stream_context(
        self, stream: str, workspace_path: Path, manual_mode: bool
    ) -> Path:
        stream_key = "b" if stream.lower().strip() == "b" else "a"
        local_app_root = self._runtime_root / stream_key / "localappdata"
        context_dir = self._get_context_dir(local_app_root)
        if context_dir is None:
            return local_app_root

        target_cfg = context_dir / "vofa+.config.json"
        target_tabviews = context_dir / "vofa+.tabviews.json"

        if not target_cfg.exists():
            baseline = self._repo_root / "presets" / "vofa" / f"baseline_{stream_key}.config.json"
            if baseline.exists():
                shutil.copy2(baseline, target_cfg)
            else:
                target_cfg.write_text("{}", encoding="utf-8")

        baseline = self._repo_root / "presets" / "vofa" / f"baseline_{stream_key}.config.json"
        if target_cfg.exists() and baseline.exists():
            try:
                payload = json.loads(target_cfg.read_text(encoding="utf-8"))
                sp = payload["ctx"]["wave_view"]["ctx"]["settingsPanel"]["ctx"]["."]
                first_name = (sp.get("settings_ctx") or [{}])[0].get("name", "")
                a_fp = first_name.startswith("mrac_pitch_e") or first_name.startswith("mrac_roll_e")
                b_fp = first_name.startswith("mrac_pitch_theta") or first_name.startswith("mrac_roll_theta")
                contaminated = (stream_key == "a" and b_fp) or (stream_key == "b" and a_fp)
                if contaminated:
                    bl = json.loads(baseline.read_text(encoding="utf-8"))
                    sp["settings_ctx"] = bl["ctx"]["wave_view"]["ctx"]["settingsPanel"]["ctx"]["."]["settings_ctx"]
                    target_cfg.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass

        if not target_tabviews.exists():
            if workspace_path.exists():
                target_tabviews.write_text(workspace_path.read_text(encoding="utf-8"), encoding="utf-8")
            else:
                src_tabviews = self._get_context_tabviews_path()
                if src_tabviews is not None and src_tabviews.exists():
                    shutil.copy2(src_tabviews, target_tabviews)
                else:
                    target_tabviews.write_text("{}", encoding="utf-8")

        if not manual_mode and workspace_path.exists():
            target_tabviews.write_text(workspace_path.read_text(encoding="utf-8"), encoding="utf-8")

        return local_app_root

    def _prepare_runtime(self, local_port: int, context_cfg: Optional[Path] = None) -> None:
        if context_cfg is None:
            context_cfg = self._get_context_config_path()
        if context_cfg is None or not context_cfg.exists():
            return
        try:
            payload = json.loads(context_cfg.read_text(encoding="utf-8"))
        except Exception:
            return

        cfg = simple_yaml_kv_load(self._config_path)
        vofa_host = str(cfg.get("vofa_host", "127.0.0.1"))
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

    def _apply_workspace_to_context(
        self, workspace_path: Path, context_tabviews: Optional[Path] = None
    ) -> bool:
        if not workspace_path.exists():
            return False
        if context_tabviews is None:
            context_tabviews = self._get_context_tabviews_path()
        if context_tabviews is None:
            return False
        try:
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
            "pitch", "roll", "yaw",
            "gyrox", "gyroy", "gyroz",
            "z_rate", "locx", "locy", "z_pos", "locxs", "locys",
        ]
        for loop in pid_loops:
            names.append(f"pid_{loop}_FB")
            names.append(f"pid_{loop}_Des")
            names.append(f"pid_{loop}_U")
        names.extend([
            "path_active_path_mode",
            "path_twc_target_x",
            "path_twc_target_y",
            "path_twc_target_z",
            "path_sinusoid_t_elapsed",
            "path_circle_theta",
            "path_twc_arrived",
        ])
        return names

    def _extract_workspace_lines(self, workspace_path: Path) -> List[int]:
        try:
            payload = json.loads(workspace_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        out: set = set()
        roots = payload.get("ctx", [])
        if not isinstance(roots, list):
            return []
        for root in roots:
            if not isinstance(root, dict):
                continue
            for tab in root.get("tabs", []):
                if not isinstance(tab, dict):
                    continue
                for widget in tab.get("widgets", []):
                    if not isinstance(widget, dict):
                        continue
                    wctx = widget.get("ctx", {})
                    if not isinstance(wctx, dict):
                        continue
                    lines = wctx.get("rbw", {}).get("ctx", {}).get(".", {}).get("lines", [])
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

    def _apply_channel_labels(
        self, stream: str, workspace_path: Path, context_cfg: Optional[Path] = None
    ) -> None:
        if context_cfg is None:
            context_cfg = self._get_context_config_path()
        if context_cfg is None or not context_cfg.exists():
            return

        if stream.lower().strip() == "b":
            names = self._build_frame_b_channel_names(self._get_max_num_basis())
        else:
            names = self._build_frame_a_channel_names()

        visible_lines = self._extract_workspace_lines(workspace_path)
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
                        new_list.append({
                            "is_draw": bool(i in line_set) if line_set else bool(old.get("is_draw", True)),
                            "color": old.get("color", "#ffffff"),
                            "scale": old.get("scale", 1),
                            "yoffset": old.get("yoffset", 0),
                            "xoffset": old.get("xoffset", 0),
                            "decimal": old.get("decimal", -7),
                            "value": old.get("value", 0),
                            "name": display_name,
                        })
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

    def _terminate_stream(self, stream: str) -> None:
        stream_key = "b" if stream.lower().strip() == "b" else "a"
        proc = self._procs.get(stream_key)
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
        self._procs[stream_key] = None
        time.sleep(0.3)

    def _terminate_instances(self, vofa_exe: str, force: bool = True) -> None:
        exe_name = Path(vofa_exe).name
        if not exe_name:
            return
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
        self._procs["a"] = None
        self._procs["b"] = None
        time.sleep(0.25)

    def _get_stream_preset_dir(self, stream: str) -> Path:
        stream_key = "b" if stream.lower().strip() == "b" else "a"
        return self._repo_root / "presets" / "vofa" / f"stream_{stream_key}"

    def _get_stream_expected_channel_names(self, stream: str) -> List[str]:
        stream_key = "b" if stream.lower().strip() == "b" else "a"
        if stream_key == "b":
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
                        rebuilt.append({
                            "is_draw": bool(old.get("is_draw", True)),
                            "color": old.get("color", "#ffffff"),
                            "scale": old.get("scale", 1),
                            "yoffset": old.get("yoffset", 0),
                            "xoffset": old.get("xoffset", 0),
                            "decimal": old.get("decimal", -7),
                            "value": old.get("value", 0),
                            "name": display_name,
                        })
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
        for fname in ("vofa+.config.json", "vofa+.tabviews.json"):
            src = preset_dir / fname
            dst = context_dir / fname
            if not dst.exists() and src.exists():
                shutil.copy2(src, dst)
        context_cfg = context_dir / "vofa+.config.json"
        if context_cfg.exists():
            self._prepare_runtime(target_port, context_cfg)
            self._repair_stream_config_channel_names(stream, context_cfg)
        return True
