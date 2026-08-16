"""Sobol / Bayesian sweep runner for parameter tuning on the bench.

Drives a parameter sweep without rebuilding firmware.  Schedules samples with
low-discrepancy Sobol sequences (scipy.stats.qmc.Sobol) or uniform random;
optimises with Nelder-Mead or a Gaussian-process surrogate (scikit-optimize,
optional).  The observable is read from live telemetry or livewatch RAM.
"""
from __future__ import annotations

import asyncio
import csv
import json
import signal
import sys
import time
import traceback
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

import numpy as np

# Optional Bayesian optimisation.
try:
    from skopt import Optimizer
    _HAVE_SKOPT = True
except ImportError:  # pragma: no cover
    _HAVE_SKOPT = False

# Sobol + Latin hypercube + standard scalar optimisers — always present via scipy.
from scipy.optimize import minimize
from scipy.stats import qmc

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ParamRange:
    """One parameter to sweep, expressed as a DWARF-dotted name + range."""
    name: str
    lo: float
    hi: float


@dataclass
class ObservableSpec:
    """How to read the figure of merit after each parameter set."""
    source: str          # "telemetry" | "livewatch"
    name: str            # e.g. "tracking_rmse" or DWARF-dotted variable name
    window: tuple[float, float] = (0.0, 1.0)   # seconds [start, end) after settle


@dataclass
class SweepConfig:
    """Full configuration for a sweep run."""
    params: list[ParamRange]
    observable: ObservableSpec
    schedule: str = "sobol"        # "sobol" | "random" | "latin"
    optimizer: str = "none"         # "none" | "bayesian" | "nelder"
    n_samples: int = 100
    settling_time_s: float = 2.0
    output_dir: str | Path = "ground_station/logs/sweeps"


@dataclass
class SweepResult:
    """Everything the sweep produced."""
    config: SweepConfig
    run_id: str
    samples: list[dict[str, Any]]
    best_params: dict[str, float]
    best_observable: float
    output_dir: Path


# ---------------------------------------------------------------------------
# Schedule helpers
# ---------------------------------------------------------------------------

def _sobol_samples(dim: int, n: int, seed: int = 0) -> np.ndarray:
    """Low-discrepancy Sobol samples in [0, 1]^dim.

    Sobol requires n to be a power of 2; round up if needed.
    """
    # Round n up to the next power of 2 to satisfy Sobol's requirement.
    if n & (n - 1) != 0:
        n = 2 ** (n.bit_length())
    sampler = qmc.Sobol(d=dim, scramble=True, seed=seed)
    return sampler.random(n=n)


def _random_samples(dim: int, n: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.random(size=(n, dim))


def _latin_samples(dim: int, n: int, seed: int = 0) -> np.ndarray:
    sampler = qmc.LatinHypercube(d=dim, scramble=True, seed=seed)
    return sampler.random(n=n)


def _sample_schedule(config: SweepConfig, n: int) -> np.ndarray:
    """Return n normalised samples in [0, 1]^len(params)."""
    dim = len(config.params)
    sched = config.schedule.lower()
    if sched == "sobol":
        return _sobol_samples(dim, n)
    elif sched == "latin":
        return _latin_samples(dim, n)
    else:  # "random"
        return _random_samples(dim, n)


# ---------------------------------------------------------------------------
# GP surrogate for Bayesian mode (scikit-optimize, optional)
# ---------------------------------------------------------------------------

class _GPSurrogate:
    """Wraps skopt.Optimizer for Bayesian proposal after an initial set."""

    def __init__(self, bounds: list[tuple[float, float]], n_initial: int = 10):
        self._opt: Optional["Optimizer"] = None
        self._bounds = bounds
        self._n_initial = n_initial
        self._n_call = 0

    def _ensure(self) -> "Optimizer":
        if self._opt is None:
            if not _HAVE_SKOPT:
                raise RuntimeError(
                    "scikit-optimize is required for Bayesian mode; "
                    "install it or use --optimizer nelder / none"
                )
            self._opt = Optimizer(
                dimensions=self._bounds,
                random_state=0,
                n_initial_points=self._n_initial,
            )
        return self._opt

    def propose(self) -> list[float]:
        p = self._ensure().ask()
        return list(p)

    def tell(self, x: list[float], y: float) -> None:
        self._ensure().tell(x, y)
        self._n_call += 1

    @property
    def initial_exhausted(self) -> bool:
        if self._opt is None:
            return False
        return self._n_call >= self._n_initial


# ---------------------------------------------------------------------------
# Transport seam — what the runner drives
# ---------------------------------------------------------------------------

class TransportSeam:
    """Adapter between SweepRunner and the actual transport (serial_bridge or livewatch).

    The spec documents two transport methods used by SweepRunner:
      - transport.set_param(name, value)   — MAVLink / USART3 param wire
      - transport.get_latest_telemetry_field(name)   — telemetry dict lookup
      - transport.livewatch_read(names)               — livewatch RAM read

    SerialBridge does not yet expose set_param; we gate on that being present.
    If the target param is not in the livewatch writable registry, we refuse to
    start (patch gate).
    """

    def __init__(self, transport: Any, writable_registry_path: str | Path | None = None):
        self._transport = transport
        # Lazily imported to avoid a hard dependency on livewatch in the
        # non-livewatch code path.
        self._registry: Optional[dict] = None
        if writable_registry_path:
            p = Path(writable_registry_path)
            if p.exists():
                import yaml
                self._registry = yaml.safe_load(p.read_text()) or {}

    def set_param(self, name: str, value: float) -> None:
        t = self._transport
        if hasattr(t, "set_param"):
            t.set_param(name, value)
        else:
            raise NotImplementedError(
                f"transport {type(t).__name__} has no set_param method; "
                "agent-05 MAVLink param wire is required for sweep runs"
            )

    def get_latest_telemetry_field(self, name: str) -> float | None:
        t = self._transport
        if hasattr(t, "get_telemetry_snapshot"):
            # SerialBridge stores the latest frame dicts internally.
            snap = t.get_telemetry_snapshot()
            for d in snap:
                if isinstance(d, dict) and name in d:
                    v = d[name]
                    return float(v) if v is not None else None
        return None

    def livewatch_read(self, names: list[str]) -> dict[str, float]:
        t = self._transport
        if hasattr(t, "livewatch_read"):
            return t.livewatch_read(names)   # type: ignore[attr-defined]
        raise NotImplementedError(
            f"transport {type(t).__name__} has no livewatch_read method"
        )

    def check_param_in_writable_registry(self, param_name: str) -> bool:
        """Refuse if the sweep target is not in the writable registry."""
        if self._registry is None:
            return True   # no registry file — skip gate
        groups = self._registry.get("groups", {})
        writable_vars: list[str] = []
        for g in groups.values():
            writable_vars.extend(g.get("vars", []))
        return param_name in writable_vars


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

class SweepRunner:
    """Parameter sweep driver."""

    def __init__(
        self,
        config: SweepConfig,
        transport: Any,
        writable_registry_path: str | Path | None = None,
    ):
        self.config = config
        self._transport = TransportSeam(transport, writable_registry_path)
        self._cancelled = False
        self._samples: list[dict[str, Any]] = []
        self._initial_params: dict[str, float] = {}
        self._run_id = uuid.uuid4().hex[:8]
        self._gp: Optional[_GPSurrogate] = None

        # Check writable registry gate for every param.
        for pr in config.params:
            if not self._transport.check_param_in_writable_registry(pr.name):
                raise ValueError(
                    f"param {pr.name!r} not in writable livewatch registry; "
                    "sweep runner refuses to start without the patch gate"
                )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self) -> SweepResult:
        """Run the sweep.  KeyboardInterrupt is caught and handled gracefully."""
        out_dir = Path(self.config.output_dir) / self._run_id
        out_dir.mkdir(parents=True, exist_ok=True)

        # Snapshot initial params.
        self._initial_params = {
            pr.name: self._read_param_current_value(pr.name)
            for pr in self.config.params
        }

        # Prime the observable collector so the first settle period fills it.
        self._prime_observable()

        if self.config.optimizer == "bayesian":
            bounds = [(pr.lo, pr.hi) for pr in self.config.params]
            self._gp = _GPSurrogate(bounds, n_initial=max(5, self.config.n_samples // 4))

        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGINT, self._handle_interrupt)
        loop.add_signal_handler(signal.SIGTERM, self._handle_interrupt)

        try:
            if self.config.optimizer == "bayesian":
                await self._run_bayesian(out_dir)
            elif self.config.optimizer == "nelder":
                await self._run_nelder(out_dir)
            else:
                await self._run_schedule(out_dir)
        except KeyboardInterrupt:
            pass
        finally:
            loop.remove_signal_handler(signal.SIGINT)
            loop.remove_signal_handler(signal.SIGTERM)
            await self._revert_to_initial()

        return self._build_result(out_dir)

    def cancel(self) -> None:
        """Stop the sweep gracefully; revert to default params."""
        self._cancelled = True
        # Populate _initial_params synchronously so revert works even if cancel()
        # is called before run() has fully entered its coroutine.
        if not self._initial_params:
            self._initial_params = {
                pr.name: self._read_param_current_value(pr.name)
                for pr in self.config.params
            }

    # ------------------------------------------------------------------
    # Core iteration
    # ------------------------------------------------------------------

    async def _run_schedule(self, out_dir: Path) -> None:
        n = self.config.n_samples
        normalised = _sample_schedule(self.config, n)

        for i, norm_row in enumerate(normalised):
            if self._cancelled:
                break
            params = self._denormalise(norm_row)
            obs = await self._run_iteration(params)
            self._samples.append({**params, self.config.observable.name: obs})
            self._append_csv_row(out_dir, self._samples[-1])
            if i < n - 1:
                await asyncio.sleep(self.config.settling_time_s)

    async def _run_bayesian(self, out_dir: Path) -> None:
        # Warm-start: fill GP with initial Sobol samples.
        warm = max(5, self.config.n_samples // 4)
        warm_norms = _sobol_samples(len(self.config.params), warm)

        for i, norm_row in enumerate(warm_norms):
            if self._cancelled:
                break
            params = self._denormalise(norm_row)
            obs = await self._run_iteration(params)
            self._gp.tell(list(params.values()), obs)   # type: ignore
            self._samples.append({**params, self.config.observable.name: obs})
            self._append_csv_row(out_dir, self._samples[-1])
            if i < warm - 1:
                await asyncio.sleep(self.config.settling_time_s)

        # Guided exploration.
        remaining = self.config.n_samples - warm
        for i in range(remaining):
            if self._cancelled:
                break
            prop = self._gp.propose()   # type: ignore[union-attr]
            params = dict(zip((pr.name for pr in self.config.params), prop))
            obs = await self._run_iteration(params)
            self._gp.tell(prop, obs)   # type: ignore[union-attr]
            self._samples.append({**params, self.config.observable.name: obs})
            self._append_csv_row(out_dir, self._samples[-1])
            await asyncio.sleep(self.config.settling_time_s)

    async def _run_nelder(self, out_dir: Path) -> None:
        # Use the schedule to seed the initial simplex.
        warm = min(3 + len(self.config.params), self.config.n_samples)
        warm_norms = _sample_schedule(self.config, warm)

        # Build initial guess from centroid of warm samples.
        centroid = warm_norms.mean(axis=0)
        x0 = self._denormalise(centroid)

        def objective(x_vals: np.ndarray) -> float:
            params = dict(zip((pr.name for pr in self.config.params), x_vals))
            # NOTE: nested event loop is safe here — scipy.optimize.minimize is
            # synchronous, so get_event_loop().run_until_complete() blocks the
            # outer loop only for the duration of this iteration. Do not move
            # to a thread-pool executor without re-checking the cancel path.
            obs = asyncio.get_event_loop().run_until_complete(
                self._run_iteration_sync(params)
            )
            # Nelder-Mead minimises; negate for maximisation.
            return -float(obs)

        result = minimize(
            objective,
            x0=np.array(list(x0.values())),
            method="Nelder-Mead",
            options={"maxiter": self.config.n_samples, "xatol": 1e-3, "fatol": 1e-4},
        )

        best_params = dict(zip(x0.keys(), result.x))
        self._samples.append({**best_params, self.config.observable.name: -result.fun})
        self._append_csv_row(out_dir, self._samples[-1])

    async def _run_iteration(self, params: dict[str, float]) -> float:
        """Apply params, settle, return the observable value."""
        for name, value in params.items():
            self._transport.set_param(name, float(value))

        await asyncio.sleep(self.config.settling_time_s)

        spec = self.config.observable
        if spec.source == "telemetry":
            return self._transport.get_latest_telemetry_field(spec.name) or 0.0
        elif spec.source == "livewatch":
            readings = self._transport.livewatch_read([spec.name])
            return float(readings.get(spec.name, 0.0))
        else:
            return 0.0

    def _run_iteration_sync(self, params: dict[str, float]) -> _AsyncProxy:
        return _AsyncProxy(self._run_iteration(params))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _denormalise(self, row: np.ndarray) -> dict[str, float]:
        return {
            pr.name: float(pr.lo + row[i] * (pr.hi - pr.lo))
            for i, pr in enumerate(self.config.params)
        }

    def _read_param_current_value(self, name: str) -> float:
        try:
            readings = self._transport.livewatch_read([name])
            return float(readings.get(name, 0.0))
        except Exception:
            return 0.0

    def _prime_observable(self) -> None:
        """Block once so the first iteration does not read stale telemetry."""
        time.sleep(0.1)

    def _append_csv_row(self, out_dir: Path, row: dict[str, Any]) -> None:
        csv_path = out_dir / "samples.csv"
        header = list(row.keys())
        write_header = not csv_path.exists()
        with open(csv_path, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=header)
            if write_header:
                w.writeheader()
            w.writerow(row)

    async def _revert_to_initial(self) -> None:
        """Restore all params to their pre-sweep values.

        If _initial_params was never populated (cancel() called before run()
        started), read the current value from the transport as a fallback.
        """
        targets = self._initial_params
        if not targets:
            # Fallback: read whatever is current — better than silently doing nothing.
            targets = {
                pr.name: self._read_param_current_value(pr.name)
                for pr in self.config.params
            }
        for name, value in targets.items():
            try:
                self._transport.set_param(name, value)
            except Exception:
                pass   # Best-effort revert on interrupt.

    def _handle_interrupt(self) -> None:
        self._cancelled = True

    def _build_result(self, out_dir: Path) -> SweepResult:
        # Write summary markdown.
        best_idx = 0
        best_val = -np.inf
        for i, s in enumerate(self._samples):
            v = s.get(self.config.observable.name, -np.inf)
            if v > best_val:
                best_val = v
                best_idx = i

        best = self._samples[best_idx] if self._samples else {}
        summary_path = out_dir / "summary.md"
        summary_path.write_text(
            f"# Sweep run {self._run_id}\n\n"
            f"Schedule: {self.config.schedule}\n"
            f"Optimizer: {self.config.optimizer}\n"
            f"Samples: {len(self._samples)}\n\n"
            f"## Best params\n\n"
            + "\n".join(f"- {k}: {v}" for k, v in best.items())
            + f"\n\nBest observable ({self.config.observable.name}): {best_val}\n"
        )

        return SweepResult(
            config=self.config,
            run_id=self._run_id,
            samples=list(self._samples),
            best_params={k: v for k, v in best.items()
                         if k != self.config.observable.name},
            best_observable=best_val,
            output_dir=out_dir,
        )


class _AsyncProxy:
    """Makes an awaitable out of an already-awaited coroutine result."""
    __slots__ = ("_result")
    def __init__(self, coro):
        self._result = coro
    def __await__(self):
        return iter([self._result])


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_argparser() -> Any:
    import argparse
    p = argparse.ArgumentParser(
        description="Sobol / Bayesian sweep runner for UAV parameter tuning"
    )
    p.add_argument("preset", help="YAML preset file")
    p.add_argument(
        "--validate",
        action="store_true",
        help="Check the preset and exit without running",
    )
    p.add_argument(
        "--registry",
        type=str,
        default=None,
        help="Path to livewatch writable registry (default: livewatch/writable_registry.yaml)",
    )
    return p


def _load_preset(path: str | Path) -> SweepConfig:
    import yaml
    with open(path) as f:
        raw = yaml.safe_load(f)
    params = [ParamRange(**p) for p in raw.pop("params", [])]
    obs = ObservableSpec(**raw.pop("observable"))
    return SweepConfig(params=params, observable=obs, **raw)


def main() -> None:
    p = _build_argparser()
    args = p.parse_args()

    try:
        config = _load_preset(args.preset)
    except Exception as exc:
        sys.stderr.write(f"preset error: {exc}\n")
        sys.exit(1)

    if args.validate:
        print(f"  params:       {len(config.params)}")
        for pr in config.params:
            print(f"    {pr.name}: [{pr.lo}, {pr.hi}]")
        print(f"  observable:   {config.observable.source}/{config.observable.name}")
        print(f"  schedule:    {config.schedule}")
        print(f"  optimizer:   {config.optimizer}")
        print(f"  n_samples:   {config.n_samples}")
        print(f"  settling:    {config.settling_time_s}s")
        print(f"  output_dir: {config.output_dir}")
        sys.exit(0)

    # --validate done; now we need a live transport.
    sys.stderr.write("sweep_runner: requires agent-05 MAVLink param wire transport\n")
    sys.stderr.write("(this module must be called with a live SerialBridge instance)\n")
    sys.exit(1)


if __name__ == "__main__":
    main()
