"""Named logging manifests: a variable set + a sample rate + a unique CSV.

A manifest is the unit an operator or an agent asks for by name ("log ekf_vs_of at
50 Hz"). It resolves to DWARF symbol paths, so any firmware variable is loggable
with no firmware change and no reflash -- the ELF is the only contract.

Rate feasibility is CHECKED, not assumed. The probe is bandwidth-limited, so a
variable set has a hard ceiling on sample rate; asking for more than that would
otherwise produce a CSV that silently logs slower than its filename claims, which
is precisely the kind of error that survives into analysis. `feasibility()` models
it offline and `calibrate()` measures it on real hardware before logging starts.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .registry import Registry

_DEFAULT_MANIFESTS = Path(__file__).with_name("manifests.yaml")

@dataclass(frozen=True)
class CostModel:
    ms_per_region: float
    ms_per_byte: float
    transport_name: str
    basis: str

    def describe(self) -> str:
        kbps = 1.0 / self.ms_per_byte
        return (f"{self.ms_per_region:.2f} ms/region + {self.ms_per_byte:.3f} ms/B, "
                f"sample at ~{kbps:.1f} KB/s ({self.basis})")


@dataclass
class Manifest:
    name: str
    vars: list[str]
    hz: float = 20.0
    doc: str = ""

    @property
    def slug(self) -> str:
        """Filename-safe stem; manifest names come from YAML keys or the CLI."""
        return "".join(c if (c.isalnum() or c in "-_") else "_" for c in self.name)


class ManifestStore:
    """Loads manifests.yaml. Missing file is fine -- ad-hoc manifests still work."""

    def __init__(self, path: str | Path | None = None, registry: Registry | None = None):
        self.path = Path(path) if path else _DEFAULT_MANIFESTS
        self.registry = registry or Registry()
        data = {}
        if self.path.exists():
            with open(self.path) as f:
                data = yaml.safe_load(f) or {}
        self._m = data.get("manifests", {})

    def names(self) -> list[str]:
        return sorted(self._m)

    def get(self, name: str) -> Manifest:
        if not name:
            raise KeyError(f"no manifest given; use one of {self.names()} or --vars")
        if name not in self._m:
            raise KeyError(f"no manifest {name!r}; have {self.names()}")
        spec = self._m[name]
        return Manifest(
            name=name,
            vars=self.registry.expand(list(spec.get("vars", []))),
            hz=float(spec.get("hz", 20.0)),
            doc=spec.get("doc", ""),
        )

    def adhoc(self, tokens: list[str], hz: float, name: str = "adhoc") -> Manifest:
        return Manifest(name=name, vars=self.registry.expand(tokens), hz=hz)


# ---------------------------------------------------------------------------
# Rate feasibility
# ---------------------------------------------------------------------------

@dataclass
class Feasibility:
    n_vars: int
    n_regions: int
    n_bytes: int
    sample_ms: float
    max_hz: float
    measured: bool = False

    def ok_for(self, hz: float, tol: float = 1.05) -> bool:
        return hz <= self.max_hz * tol

    def describe(self) -> str:
        how = "measured" if self.measured else "estimated"
        return (f"{self.n_vars} vars / {self.n_regions} region(s) / {self.n_bytes} B "
                f"-> {self.sample_ms:.2f} ms per sample, max {self.max_hz:.0f} Hz ({how})")


def feasibility(plan, cost_model: CostModel) -> Feasibility:
    """Offline estimate from a transport's cost model. No hardware needed."""
    n_bytes = sum(r.size for r in plan.regions)
    n_regions = len(plan.regions)
    ms = (cost_model.ms_per_region * n_regions
          + cost_model.ms_per_byte * n_bytes)
    return Feasibility(len(plan.symbols), n_regions, n_bytes, ms, 1000.0 / ms, measured=False)


def calibrate(reader, plan, cost_model: CostModel, n: int = 15) -> Feasibility:
    """Measure the real per-sample cost against the attached target.

    Uses the median, not the mean: the probe emits occasional multi-hundred-ms
    outliers on USB retries, and a mean would let one of those understate the
    achievable rate badly.
    """
    base = feasibility(plan, cost_model=cost_model)
    times = []
    for _ in range(n):
        t0 = time.perf_counter()
        reader.sample(plan)
        times.append((time.perf_counter() - t0) * 1000.0)
    times.sort()
    ms = times[len(times) // 2]
    return Feasibility(base.n_vars, base.n_regions, base.n_bytes, ms, 1000.0 / ms, measured=True)


# ---------------------------------------------------------------------------
# Output naming
# ---------------------------------------------------------------------------

def unique_csv_path(outdir: str | Path, manifest: Manifest, hz: float,
                    when: float | None = None) -> Path:
    """<outdir>/<slug>_<hz>hz_<YYYYmmdd-HHMMSS>.csv, collision-suffixed.

    The rate is in the name because the same manifest logged at different rates
    produces datasets that must never be confused for one another.
    """
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(when or time.time()))
    stem = f"{manifest.slug}_{hz:g}hz_{stamp}"
    path = outdir / f"{stem}.csv"
    n = 2
    while path.exists():
        path = outdir / f"{stem}_{n}.csv"
        n += 1
    return path


def _elf_fingerprint(elf: str | Path) -> dict:
    p = Path(elf)
    h = hashlib.sha256(p.read_bytes()).hexdigest()[:16] if p.exists() else None
    return {"path": str(p), "sha256_16": h,
            "mtime": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(p.stat().st_mtime))
            if p.exists() else None}


def write_meta(csv_path: Path, manifest: Manifest, plan, elf: str | Path,
               requested_hz: float, feas: Feasibility, extra: dict | None = None) -> Path:
    """Sidecar JSON describing exactly how this CSV was produced.

    The symbol addresses are only meaningful against the build they came from, so
    the ELF fingerprint is recorded alongside them; a log analysed against the
    wrong firmware would otherwise be silently misinterpreted.
    """
    meta = {
        "manifest": {"name": manifest.name, "doc": manifest.doc,
                     "vars": manifest.vars, "hz": manifest.hz},
        "requested_hz": requested_hz,
        "feasibility": {"n_vars": feas.n_vars, "n_regions": feas.n_regions,
                        "n_bytes": feas.n_bytes, "sample_ms": round(feas.sample_ms, 3),
                        "max_hz": round(feas.max_hz, 1), "measured": feas.measured},
        "symbols": [{"name": s.name, "addr": f"0x{s.address:08X}", "size": s.size}
                    for s in plan.symbols],
        "regions": [{"start": f"0x{r.start:08X}", "size": r.size} for r in plan.regions],
        "elf": _elf_fingerprint(elf),
        "transport": "swd-cmsis-dap",
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    if extra:
        meta.update(extra)
    path = csv_path.with_suffix(".meta.json")
    path.write_text(json.dumps(meta, indent=2))
    return path
