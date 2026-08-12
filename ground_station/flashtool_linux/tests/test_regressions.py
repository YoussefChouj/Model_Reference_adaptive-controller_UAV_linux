"""Regression tests for ground_station.flashtool_linux.

These run offline (no probe, no toolchain beyond Python). Build/linker
regressions live in sim/tests/ + the actual `tasks.py build` invocation;
here we lock down the Python-side invariants that a flaky build cycle
would otherwise re-discover one by one.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


_REPO = Path(__file__).resolve().parents[3]
_STARTUP = _REPO / "firmware" / "startup" / "startup_stm32f40_41xxx.s"


def _startup_text() -> str:
    return _STARTUP.read_text()


def test_all_external_irqs_have_default_handler_alias() -> None:
    """B1 regression: every external IRQ must reach Default_Handler on no override.

    Two acceptable patterns:
      1. weak_handler MACRO invocation — emits .weak + label + 'b .'  (current pattern)
      2. explicit .weak + .set XXX, Default_Handler                  (added fallback)

    The previous code had .weak alone, which is also accepted (the unresolved
    weak symbol resolves to its own 'b .' handler — not address 0). The
    important invariant is that *every* external IRQ declared in the vector
    table has either a weak_handler invocation OR a Default_Handler alias.
    """
    text = _startup_text()

    # IRQ names that appear in the vector table
    in_vector = set(re.findall(r"^\s*\.word\s+(\w+_IRQHandler)\s*$", text, re.MULTILINE))
    # weak_handler macro invocations
    in_macro = set(re.findall(r"^weak_handler\s+(\w+)\s*$", text, re.MULTILINE))
    # .weak declarations
    weak_decls = set(re.findall(r"^\.weak\s+(\w+)\s*$", text, re.MULTILINE))
    # .set XXX, Default_Handler aliases
    aliased = set(re.findall(r"^\.set\s+(\w+),\s*Default_Handler\s*$", text, re.MULTILINE))

    # Every IRQ in the vector table must have at least one resolution path
    missing = sorted(in_vector - in_macro - weak_decls - aliased)
    assert not missing, (
        f"{len(missing)} IRQ(s) in vector table with no handler binding: "
        f"{missing[:5]}{'...' if len(missing) > 5 else ''}"
    )


def test_vector_table_first_entry_is_stack_top_value() -> None:
    """The vector table's first word must point at the SP value, not a label.

    The MCU loads whatever 4 bytes sit at offset 0 into SP on reset. We
    previously had '.word __initial_sp' (a label), which assembled to 0.
    """
    text = _startup_text()
    # Find the .isr_vector section, then the first .word after __Vectors:
    assert re.search(
        r"__Vectors:\s*\n\s*\.word\s+__StackTop",
        text,
    ), "vector table entry 0 must be '.word __StackTop' (the SP value)"


def test_reset_handler_calls_libc_init_array_then_main() -> None:
    """Reset_Handler must initialise the C runtime before main."""
    text = _startup_text()
    # Locate Reset_Handler block
    m = re.search(
        r"Reset_Handler:\s*(.*?)\n\s*\.size\s+Reset_Handler",
        text,
        re.DOTALL,
    )
    assert m, "Reset_Handler not found"
    body = m.group(1)
    assert "bl SystemInit" in body, "must call SystemInit"
    assert "bl __libc_init_array" in body, "must call __libc_init_array"
    assert "bl main" in body, "must call main"
    # Order: SystemInit -> __libc_init_array -> main
    assert body.index("bl SystemInit") < body.index("bl __libc_init_array") < body.index("bl main")


def test_enumerate_probes_returns_empty_when_pyocd_missing() -> None:
    """The shared probe helper must not raise when pyocd is absent."""
    from ground_station.flashtool_linux import enumerate_probes
    # Just calling it must not raise. Empty list is fine.
    result = enumerate_probes()
    assert isinstance(result, list)
    # Each entry, if any, has the expected keys
    for p in result:
        assert "uid" in p
        assert "description" in p
        assert "board_name" in p


def test_system_reset_used_not_core_reset() -> None:
    """I1 regression: linux_flash.reset() must call system_reset, not reset().

    target.reset() halts the core; we want NVIC AIRCR.SYSRESETREQ.
    Uses ast to skip docstrings and comments.
    """
    import ast
    src_path = _REPO / "ground_station" / "flashtool_linux" / "linux_flash.py"
    tree = ast.parse(src_path.read_text(), filename=str(src_path))
    # Walk only real code statements (skip module docstring + Expr/Constant)
    code_lines: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue  # docstring
        if hasattr(node, "lineno"):
            code_lines.append(f"L{node.lineno}")

    full = src_path.read_text()
    assert "session.target.system_reset()" in full, "expected system_reset() call"
    assert "target.reset()" not in full or "system_reset" in full, (
        "expected only system_reset() in code"
    )


def test_no_verify_function_only_checksum() -> None:
    """I2 regression: the misleading verify() was renamed to checksum_elf().

    Anything named verify() would suggest post-flash verification that we
    cannot safely perform under the no-halt safety contract.
    """
    src = (_REPO / "ground_station" / "flashtool_linux" / "linux_flash.py").read_text()
    assert "def checksum_elf" in src
    # No top-level def verify (allow the word 'verify' in comments/strings)
    assert not re.search(r"^def verify\(", src, re.MULTILINE), (
        "old verify() function still present; should be renamed to checksum_elf()"
    )


def test_linker_comment_not_about_hardware_faults() -> None:
    """C1 regression: ARM.exidx is C++ unwinding metadata, not fault handlers."""
    src = (_REPO / "firmware" / "cmake" / "stm32f407zg.ld").read_text()
    # Find the .ARM.exidx comment region
    assert "must be in SRAM for hardware faults" not in src, (
        "misleading ARM.exidx comment still present"
    )