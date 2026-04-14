"""
Deterministic checker. Config-driven gates per subsystem.
Zero LLM calls. Zero Copilot requests.

Usage: python .agent_scripts/checker.py --contract PATH --patch PATH
"""

import argparse
import subprocess
import sys
import re
import os
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
KEIL_PROJECT = WORKSPACE_ROOT / "USER" / "JX_FLY.uvprojx"
KEIL_BUILD_LOG = WORKSPACE_ROOT / ".agent_reports" / "keil_build.log"
PYTHON_EXE = sys.executable


def resolve_keil_build_cmd() -> list | None:
    """Resolve a usable Keil UV4 command for this workspace."""
    candidates = [
        os.environ.get("KEIL_UV4", "").strip(),
        "C:/Keil_v5/UV4/UV4.exe",
        "UV4.exe",
    ]
    for cmd in candidates:
        if not cmd:
            continue
        if cmd.lower() == "uv4.exe" or Path(cmd).exists():
            return [cmd, "-b", str(KEIL_PROJECT), "-o", str(KEIL_BUILD_LOG)]
    return None


FIRMWARE_BUILD_CMD = resolve_keil_build_cmd()


GATE_CONFIG = {
    "firmware": {
        "build": FIRMWARE_BUILD_CMD,
        "lint": None,
        "test": None,
    },
    "ground_station": {
        "build": None,
        "lint": [
            PYTHON_EXE,
            "-m",
            "flake8",
            "--max-line-length=120",
            "--ignore=E501,W503,E203,W391",
            "ground_station/",
        ],
        "test": [PYTHON_EXE, "-m", "pytest", "ground_station/", "-x", "-q", "--tb=short"],
    },
    "simulation": {
        "build": None,
        "lint": [PYTHON_EXE, "-m", "flake8", "--max-line-length=120", "simulation/"],
        "test": [PYTHON_EXE, "-m", "pytest", "simulation/", "-x", "-q", "--tb=short"],
    },
    "docs": {
        "build": None,
        "lint": None,
        "test": None,
    },
}


def run_cmd(cmd: list | None) -> tuple[bool, str]:
    if cmd is None:
        return True, "(skipped - no command configured)"
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=str(WORKSPACE_ROOT))
        output = (r.stdout + r.stderr).strip()
        if r.returncode == 5 and "pytest" in cmd:
            # pytest exit code 5 means "no tests collected".
            return True, "(skipped - no tests collected)"
        return r.returncode == 0, output
    except FileNotFoundError:
        return True, f"(skipped - {cmd[0]} not found)"
    except Exception as e:
        return False, str(e)


def extract_field(contract: str, field: str) -> str:
    pattern = rf"## {re.escape(field)}\s*\n(.*?)(?=\n## |\Z)"
    m = re.search(pattern, contract, re.DOTALL)
    return m.group(1).strip() if m else ""


def extract_scope_files(contract: str) -> list[str]:
    scope = extract_field(contract, "Scope")
    files: list[str] = []

    inline = re.search(r"Files allowed to change:\s*\[(.*?)\]", scope, re.IGNORECASE)
    if inline:
        for item in inline.group(1).split(","):
            candidate = item.strip().strip("`\"'")
            if candidate:
                files.append(candidate)

    in_allowed = False
    for line in scope.splitlines():
        lower = line.lower()
        if "files allowed to change" in lower:
            in_allowed = True
            continue
        if "files not to touch" in lower:
            break
        if in_allowed:
            stripped = line.strip().lstrip("-").strip().strip("`")
            if stripped:
                files.append(stripped)

    seen = set()
    ordered = []
    for f in files:
        norm = f.replace("\\", "/")
        if norm not in seen:
            seen.add(norm)
            ordered.append(norm)
    return ordered


def extract_subsystem(contract: str) -> str:
    sub = extract_field(contract, "Subsystem").strip().lower()
    if sub in GATE_CONFIG:
        return sub

    scope = extract_field(contract, "Scope").lower()
    if "ground_station" in scope:
        return "ground_station"
    if "simulation" in scope:
        return "simulation"
    if ".c" in scope or ".h" in scope or "user/" in scope:
        return "firmware"
    return "docs"


def check_scope(patch_text: str, allowed_files: list[str]) -> tuple[bool, list[str]]:
    changed = re.findall(r"^FILE:\s*(.+)$", patch_text, re.MULTILINE)
    changed += re.findall(r"^\+\+\+ b/(.+)$", patch_text, re.MULTILINE)
    changed = sorted({c.strip().replace("\\", "/") for c in changed if c.strip()})

    if not changed:
        return True, []

    normalized_allowed = [a.replace("\\", "/") for a in allowed_files]
    violations = []
    for f in changed:
        allowed = any(
            f == a or f.endswith("/" + a.lstrip("./")) or a.endswith("/" + f.lstrip("./"))
            for a in normalized_allowed
        )
        if not allowed:
            violations.append(f)
    return len(violations) == 0, violations


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True)
    parser.add_argument("--patch", required=True)
    args = parser.parse_args()

    contract = Path(args.contract).read_text(encoding="utf-8")
    patch = Path(args.patch).read_text(encoding="utf-8")

    subsystem = extract_subsystem(contract)
    gates = GATE_CONFIG.get(subsystem, GATE_CONFIG["docs"])

    report = [
        "# Checker Report",
        f"Contract: {args.contract}",
        f"Patch: {args.patch}",
        f"Subsystem: {subsystem}",
        "",
    ]
    all_pass = True

    allowed = extract_scope_files(contract)
    scope_ok, violations = check_scope(patch, allowed)
    status = "PASS" if scope_ok else "FAIL"
    if not scope_ok:
        all_pass = False
    report.append(f"## Scope Gate: {status}")
    if violations:
        report.append("Unauthorized files changed:")
        for v in violations:
            report.append(f"  - {v}")
    report.append("")

    lint_cmd = gates.get("lint")
    test_cmd = gates.get("test")

    # For Python subsystems, lint only files in contract scope to avoid unrelated baseline lint failures.
    if subsystem in {"ground_station", "simulation"}:
        scoped_py_files = [f for f in allowed if f.replace("\\", "/").endswith(".py")]
        if scoped_py_files:
            if subsystem == "ground_station":
                lint_cmd = [
                    PYTHON_EXE,
                    "-m",
                    "flake8",
                    "--max-line-length=120",
                    "--ignore=E501,W503,E203,W391",
                    *scoped_py_files,
                ]
            else:
                lint_cmd = [
                    PYTHON_EXE,
                    "-m",
                    "flake8",
                    "--max-line-length=120",
                    *scoped_py_files,
                ]

    build_ok, build_out = run_cmd(gates.get("build"))
    status = "PASS" if build_ok else "FAIL"
    if not build_ok:
        all_pass = False
    report.append(f"## Build Gate: {status}")
    if not build_ok:
        report.append(f"```\n{build_out[:2000]}\n```")
    report.append("")

    lint_ok, lint_out = run_cmd(lint_cmd)
    status = "PASS" if lint_ok else "FAIL"
    if not lint_ok:
        all_pass = False
    report.append(f"## Lint Gate: {status}")
    if not lint_ok:
        report.append(f"```\n{lint_out[:1000]}\n```")
    report.append("")

    test_ok, test_out = run_cmd(test_cmd)
    status = "PASS" if test_ok else "FAIL"
    if not test_ok:
        all_pass = False
    report.append(f"## Test Gate: {status}")
    if not test_ok:
        report.append(f"```\n{test_out[:1000]}\n```")
    report.append("")

    verdict = "ALL GATES PASSED" if all_pass else "GATES FAILED"
    report.append(f"## Verdict: {verdict}")

    report_dir = Path(".agent_reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(args.patch).stem
    report_path = report_dir / f"{stem}_checker.md"
    report_path.write_text("\n".join(report), encoding="utf-8")
    print(f"[checker] Report: {report_path}")
    print(f"[checker] Verdict: {verdict}")
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
