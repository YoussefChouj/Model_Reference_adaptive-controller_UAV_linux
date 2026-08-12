"""CLI entry point for ground_station.flashtool_linux.

Usage:
    python -m ground_station.flashtool_linux build          # cmake configure + build
    python -m ground_station.flashtool_linux flash HEX      # flash HEX file
    python -m ground_station.flashtool_linux probe-info     # enumerate probes
    python -m ground_station.flashtool_linux preflight      # pre-flight checks
    python -m ground_station.flashtool_linux all            # build + flash
    python -m ground_station.flashtool_linux doctor         # toolchain + probe checks
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import linux_build, linux_flash, linux_preflight


def _report(r) -> None:
    print(r.report())


def cmd_build(argv: argparse.Namespace) -> int:
    res = linux_build.all(jobs=argv.jobs)
    _report(res)
    return 0 if res.ok else 1


def cmd_flash(argv: argparse.Namespace) -> int:
    pf = linux_preflight.run_all()
    print(pf.report())
    if not pf.ok:
        return 1

    hex_path = Path(argv.hex)
    if not hex_path.is_absolute():
        hex_path = Path(linux_build._ROOT / hex_path)

    res = linux_flash.flash(hex_path, frequency_hz=argv.frequency)
    _report(res)
    return 0 if res.ok else 1


def cmd_all(argv: argparse.Namespace) -> int:
    print("=== build ===")
    res = linux_build.all(jobs=argv.jobs)
    _report(res)
    if not res.ok:
        return 1

    hex_path = linux_build._HEX
    print(f"\n=== flash {hex_path} ===")
    pf = linux_preflight.run_all()
    print(pf.report())
    if not pf.ok:
        return 1

    fr = linux_flash.flash(hex_path, frequency_hz=argv.frequency)
    _report(fr)
    return 0 if fr.ok else 1


def cmd_reset(argv: argparse.Namespace) -> int:
    ok = linux_flash.reset()
    print(f"[reset] {'ok' if ok else 'FAIL'}")
    return 0 if ok else 1


def cmd_probe_info(argv: argparse.Namespace) -> int:
    """Enumerate connected probes via offline pyocd APIs (no probe required)."""
    info = linux_flash.probe_info()
    print(f"Target: {info['target']}")
    if info.get("error"):
        print(f"  (probe enumeration error: {info['error']})")
    if info["probes"]:
        for p in info["probes"]:
            print(f"  probe uid={p['uid']}  board={p['board_name']}  {p['description']}")
    else:
        print("  (no probes enumerated)")
    return 0


def cmd_preflight(argv: argparse.Namespace) -> int:
    res = linux_preflight.run_all()
    print(res.report())
    return 0 if res.ok else 1


def cmd_doctor(argv: argparse.Namespace) -> int:
    """Toolchain + probe checks; used by tasks.py doctor integration."""
    tc = linux_preflight.toolchain_present()
    print(f"[doctor] arm-none-eabi-gcc  {'ok' if tc.ok else 'MISSING'}")
    if not tc.ok:
        print(f"         {tc.details.get('arm-none-eabi-gcc', '')}")

    info = linux_flash.probe_info()
    probes = info["probes"]
    print(f"[doctor] CMSIS-DAP probes  {'ok' if probes else 'none'} ({len(probes)} found)")
    for p in probes:
        print(f"         uid={p['uid']}  {p['description']}")

    if probes and tc.ok:
        print("[doctor] READY")
        return 0
    print("[doctor] ISSUES — run scripts/setup_linux_toolchain.sh")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Linux-native ARM firmware build + flash",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("build", help="cmake configure + build")
    p.add_argument("-j", "--jobs", type=int, default=None,
                   help="parallel jobs (default: auto)")

    p = sub.add_parser("flash", help="flash a .hex file")
    p.add_argument("hex", help="path to .hex file")
    p.add_argument("--frequency", type=int, default=5_000_000,
                   help="SWD clock Hz (default: 5000000)")

    p = sub.add_parser("all", help="build + flash (full loop)")
    p.add_argument("-j", "--jobs", type=int, default=None,
                   help="parallel build jobs (default: auto)")
    p.add_argument("--frequency", type=int, default=5_000_000,
                   help="SWD clock Hz (default: 5000000)")

    sub.add_parser("reset", help="system reset over SWD")
    sub.add_parser("probe-info", help="enumerate connected probes")
    sub.add_parser("preflight", help="run pre-flight checks")
    sub.add_parser("doctor", help="toolchain + probe status (tasks.py integration)")

    argv = parser.parse_args(sys.argv[1:] if sys.argv[1:] else ["doctor"])

    handlers = {
        "build": cmd_build,
        "flash": cmd_flash,
        "all": cmd_all,
        "reset": cmd_reset,
        "probe-info": cmd_probe_info,
        "preflight": cmd_preflight,
        "doctor": cmd_doctor,
    }

    handler = handlers.get(argv.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(argv)


if __name__ == "__main__":
    sys.exit(main())
