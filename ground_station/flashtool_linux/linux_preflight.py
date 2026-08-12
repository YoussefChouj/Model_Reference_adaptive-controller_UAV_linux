"""Linux pre-flight checks for flashtool_linux.

Two checks gate every probe operation:
  1. arm-none-eabi-gcc present (toolchain on PATH)
  2. CMSIS-DAP probe enumerable (not held by another process)

Unlike the Windows preflight (which checks for uVision holding the CMSIS-DAP
singleton), Linux has no equivalent Keil process — the second check alone
is sufficient.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass


@dataclass
class LinuxPreflightResult:
    ok: bool
    failed: list[str]
    details: dict[str, str]

    def report(self) -> str:
        if self.ok:
            return "[preflight] ok — toolchain + probe available"
        head = "[preflight] BLOCKED"
        lines = [head]
        for name in self.failed:
            lines.append(f"    ! {name}: {self.details.get(name, '?')}")
        return "\n".join(lines)


def toolchain_present() -> LinuxPreflightResult:
    """Is arm-none-eabi-gcc on PATH?"""
    path = shutil.which("arm-none-eabi-gcc")
    if path:
        return LinuxPreflightResult(ok=True, failed=[], details={})
    return LinuxPreflightResult(
        ok=False,
        failed=["arm-none-eabi-gcc"],
        details={"arm-none-eabi-gcc": "not on PATH — run scripts/setup_linux_toolchain.sh"},
    )


def cmsis_dap_present() -> LinuxPreflightResult:
    """Is a CMSIS-DAP probe enumerated and not held by another process?"""
    from pyocd.probe.cmsis_dap_probe import CMSISDAPProbe
    try:
        probes = CMSISDAPProbe.get_all_connected_probes()
    except Exception as exc:
        return LinuxPreflightResult(
            ok=False,
            failed=["cmsis_dap"],
            details={"cmsis_dap": f"pyocd error: {exc}"},
        )
    if not probes:
        return LinuxPreflightResult(
            ok=False,
            failed=["cmsis_dap"],
            details={
                "cmsis_dap": (
                    "no probe enumerated — check USB connection, "
                    "or another process holds the probe (uVision debug session, livewatch)"
                )
            },
        )
    return LinuxPreflightResult(ok=True, failed=[], details={})


def run_all() -> LinuxPreflightResult:
    """Run all Linux pre-flight checks. Return combined result."""
    results = [toolchain_present(), cmsis_dap_present()]
    failed: list[str] = []
    details: dict[str, str] = {}
    for r in results:
        if not r.ok:
            failed.extend(r.failed)
            details.update(r.details)
    return LinuxPreflightResult(ok=not failed, failed=failed, details=details)
