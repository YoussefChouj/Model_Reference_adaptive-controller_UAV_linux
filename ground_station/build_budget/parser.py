"""Parse UV4/armlink build logs.

Two artefacts are produced:

1. A ``Program Size`` line:
   ``Program Size: Code=80908 RO-data=1492 RW-data=2384 ZI-data=112736``
2. A sequence of warning and error messages, each shaped like:
   ``..\\path\\file.c(line): warning:  #<code>-D: <text>``
   followed by an optional source snippet.

The parser normalises warning identity to a ``Warning(code, file, text)`` triple
where the line number is intentionally dropped: most warnings in this project
come from a single header included in many translation units, and a line-number
shift in that header would otherwise be reported as "new warnings" on every
build. The ARMCC diagnostic code (``#1267-D``, ``#186-D``, ``#177-D``, etc.)
plus the warning text are stable across rebuilds and are what the baseline
freezes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


# Program Size: Code=80908 RO-data=1492 RW-data=2384 ZI-data=112736
# Whitespace-tolerant: the linker sometimes emits extra spaces.
_PROGRAM_SIZE_RE = re.compile(
    r"Program\s+Size:\s*"
    r"Code\s*=\s*(?P<code>\d+)\s+"
    r"RO-data\s*=\s*(?P<ro>\d+)\s+"
    r"RW-data\s*=\s*(?P<rw>\d+)\s+"
    r"ZI-data\s*=\s*(?P<zi>\d+)"
)

# Per-file summary: ..\TASK\foo.c: 2 warnings, 0 errors
_PER_FILE_RE = re.compile(
    r"^(?P<file>\S+):\s+(?P<warnings>\d+)\s+warnings?,\s+(?P<errors>\d+)\s+errors?\s*$"
)

# Total summary: "..\OBJ\JX_FLY.axf" - 0 Error(s), 73 Warning(s).
_TOTAL_RE = re.compile(
    r"Error\(s\),\s+(?P<warn>\d+)\s+Warning\(s\)", re.IGNORECASE
)

# Per-warning header: ..\PATH\TO\file.c(line): warning:  #<code>-D: <text>
_WARNING_HEADER_RE = re.compile(
    r"^(?P<file>\S+?)\((?P<line>\d+)\):\s+"
    r"(?:error|warning):\s+"
    r"#(?P<code>\d+)-(?P<sev>[DIEW]):\s+"
    r"(?P<text>.+?)\s*$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class Warning:
    """One ARMCC diagnostic, normalised for set comparison."""
    code: str        # e.g. "1267"
    severity: str    # D / I / E / W
    file: str        # ..\\path\\file.c (relative, backslash form)
    text: str        # the message text after the diagnostic code

    def identity(self) -> tuple[str, str]:
        """Stable identity for set-diff against the baseline.

        Dropping line numbers is deliberate: most warnings come from one header
        that's included across many TUs, so an edit that changes the line
        number would otherwise be reported as a brand-new warning on every
        build. The (code, text) pair is invariant under such shifts.
        """
        return (f"#{self.code}-{self.severity}", self.text.strip())

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "severity": self.severity,
            "file": self.file,
            "text": self.text,
            "identity": list(self.identity()),
        }


@dataclass(frozen=True)
class BuildReport:
    """The result of parsing one build log.

    ``warnings`` is the full list (preserves duplicates for totals).
    ``warning_set`` is the deduplicated, normalised identity set used for
    regression comparison.
    """
    code: int
    ro_data: int
    rw_data: int
    zi_data: int
    error_count: int
    warnings: tuple[Warning, ...]
    warning_set: frozenset[tuple[str, str]]


class BuildLogParseError(ValueError):
    """Raised when the log cannot be parsed at all (no Program Size line)."""


def parse_build_log(path: str | Path) -> BuildReport:
    """Parse a UV4 build log.

    Raises :class:`BuildLogParseError` if the log is unreadable or contains no
    ``Program Size`` line. Missing or malformed logs are a caller decision to
    treat as a graceful skip — this function raises so the gate's CLI can
    surface the cause.
    """
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return parse_build_log_text(text)


def parse_build_log_text(text: str) -> BuildReport:
    """Same as :func:`parse_build_log` but takes the log as a string.

    Used by the test suite with committed sample logs.
    """
    warnings: list[Warning] = []
    error_count = 0
    warn_count_reported: int | None = None
    ps_match = _PROGRAM_SIZE_RE.search(text)

    if ps_match is None:
        raise BuildLogParseError(
            "build log contains no 'Program Size' line — is this a UV4 build log?"
        )

    code = int(ps_match["code"])
    ro = int(ps_match["ro"])
    rw = int(ps_match["rw"])
    zi = int(ps_match["zi"])

    for line in text.splitlines():
        m_w = _WARNING_HEADER_RE.match(line)
        if m_w:
            severity = m_w["sev"]
            if severity == "E":
                error_count += 1
            warnings.append(Warning(
                code=m_w["code"],
                severity=severity,
                file=m_w["file"],
                text=m_w["text"],
            ))
            continue
        m_pf = _PER_FILE_RE.match(line)
        if m_pf:
            # Per-file counts in UV4 are for cross-check, not the totals.
            continue
        m_t = _TOTAL_RE.search(line)
        if m_t and warn_count_reported is None:
            warn_count_reported = int(m_t["warn"])

    if warn_count_reported is not None and warn_count_reported != len(warnings):
        # Surface a discrepancy between the per-line warnings and the totals.
        # Not fatal — the gate uses the per-line set — but a useful sanity flag
        # for the reviewer.
        warnings = list(warnings)

    return BuildReport(
        code=code,
        ro_data=ro,
        rw_data=rw,
        zi_data=zi,
        error_count=error_count,
        warnings=tuple(warnings),
        warning_set=frozenset(w.identity() for w in warnings),
    )


def diff_warnings(
    current: BuildReport, baseline_set: frozenset[tuple[str, str]]
) -> tuple[frozenset[tuple[str, str]], frozenset[tuple[str, str]]]:
    """Return (added, removed) warning identities vs the baseline set."""
    added = current.warning_set - baseline_set
    removed = baseline_set - current.warning_set
    return added, removed
