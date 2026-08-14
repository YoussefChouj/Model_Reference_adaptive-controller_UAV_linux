"""SINDy-style fit engine for the interactive PX4 viewer.

This module is the math layer beneath ``sim.sindy.viewer``. It separates
the regression from the rendering so the fits are testable without
plotly. The viewer passes in time-aligned ``(x, u, dx)`` arrays; this
module returns:

- per-axis polynomial library fits (linear + quadratic + cross terms in
  ``(x, u)``)
- a joint cross-axis fit that treats ``(x_roll, x_pitch, x_yaw, u_roll,
  u_pitch, u_yaw)`` as a 6-vector and fits the polynomial library once,
  producing a coefficient matrix ``Θ ∈ R^(27 features × 3 outputs)``

The fits expose coefficients and metrics so the viewer can build a
comprehensive per-feature toggle UI: every feature term maps to a row
of the coefficient matrix, and un-checking a feature in the UI means
"refit with that column dropped from Φ". The recompute is OLS on a
small matrix, so this is cheap.

The math is plain linear least squares with a STLSQ-style threshold for
sparsity. We deliberately do not invoke ``sim.sindy.fitter.fit_sindy``:
that helper is scoped for the canonical ``[e, x, xm]`` problem and
expects a 3-feature input. The viewer is a different entry point with
its own feature library, and we keep the seams clean.

Notation
--------
- ``x`` : plant state (rad/s) — body rate in our case
- ``u`` : control input — body-rate setpoint in our case
- ``dx`` : discrete-time derivative ``(x[k+1] - x[k-1]) / (2*dt)``

Feature library (per axis): degree-2 polynomial in ``(x, u)`` with no
cross-constant term (we don't fit a bias; the controller's nominal
dynamics subsume it):

  - ``x``
  - ``u``
  - ``x^2``
  - ``x*u``
  - ``u^2``

That's 5 features per axis. Including a bias gives 6 — we offer both
via ``FitConfig``.

Joint feature library (degree 2 in 6-vector ``[x_r, x_p, x_y, u_r,
u_p, u_y]``): linear (6) + quadratic (21) = 27 features. The mapping
from feature index to ``(i, j)`` pairs is exposed via ``JOINT_FEATURE_NAMES``
so the viewer can label rows.

Public API
----------
- ``FitConfig`` : dataclass controlling bias inclusion, train/test split,
  STLSQ threshold, n_active ratio
- ``per_axis_fit(t, x, u, dx, cfg)`` : single-axis fit
- ``joint_fit(per_axis_inputs, cfg)`` : 6-state cross-axis fit
- ``compute_metrics(y_true, y_pred, n_active, n_total)`` : metric dict
- ``PER_AXIS_FEATURE_NAMES`` : ``["x", "u", "x^2", "x*u", "u^2"]`` (+bias)
- ``JOINT_FEATURE_NAMES`` : 27 polynomial-feature names for 6-vector
- ``METRIC_NAMES`` : tuple of metric keys returned in the metrics dict
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

import numpy as np


# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

PER_AXIS_FEATURES_NO_BIAS: tuple[str, ...] = (
    "x",
    "u",
    "x^2",
    "x*u",
    "u^2",
)
PER_AXIS_FEATURES_WITH_BIAS: tuple[str, ...] = ("1",) + PER_AXIS_FEATURES_NO_BIAS

# 6-vector: [x_r, x_p, x_y, u_r, u_p, u_y]
# Linear (6) + quadratic (C(6+2-1, 2) = 21) = 27 features, no constant.
JOINT_INPUT_NAMES: tuple[str, ...] = ("x_r", "x_p", "x_y", "u_r", "u_p", "u_y")
JOINT_FEATURE_NAMES: tuple[str, ...] = (
    # linear
    "x_r", "x_p", "x_y", "u_r", "u_p", "u_y",
    # quadratic (i <= j, upper-triangular enumeration)
    "x_r^2", "x_r*x_p", "x_r*x_y", "x_r*u_r", "x_r*u_p", "x_r*u_y",
    "x_p^2",          "x_p*x_y", "x_p*u_r", "x_p*u_p", "x_p*u_y",
    "x_y^2",                   "x_y*u_r", "x_y*u_p", "x_y*u_y",
    "u_r^2",                   "u_r*u_p", "u_r*u_y",
    "u_p^2",                   "u_p*u_y",
    "u_y^2",
)
# Sanity-check: name count matches the linear + quadratic combinatorics.
assert len(JOINT_FEATURE_NAMES) == 6 + (6 * 7) // 2, (
    f"JOINT_FEATURE_NAMES has {len(JOINT_FEATURE_NAMES)} entries; "
    "expected 6 linear + C(8,2) quadratic = 27"
)

METRIC_NAMES: tuple[str, ...] = (
    "r2_train", "r2_test",
    "mse_train", "mse_test",
    "rmse_train", "rmse_test",
    "mae_train", "mae_test",
    "nrmse_train", "nrmse_test",
    "n_active_terms", "n_total_terms",
    "library",
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FitConfig:
    """Configuration shared by per-axis and joint fits.

    Attributes
    ----------
    include_bias
        If True, prepend a constant column to Φ so the model can fit a
        DC offset. Default False — the controller's nominal dynamics
        already cover offsets and adding a bias tends to swallow the
        "small but real" coefficients we want to see.
    train_fraction
        Fraction of samples used for fitting; the rest are the held-out
        test set. Default 0.8.
    seed
        RNG seed for the deterministic 80/20 split. Set to 0 to disable
        shuffling (use the first train_fraction as train).
    threshold
        STLSQ-style threshold on |coef|; coefs below this are set to
        zero. Default 0.05. Smaller threshold ⇒ denser solution.
    max_iter
        STLSQ iterations. Default 5.
    """
    include_bias: bool = False
    train_fraction: float = 0.8
    seed: int = 42
    threshold: float = 0.05
    max_iter: int = 5

    def __post_init__(self) -> None:
        if not 0.0 < self.train_fraction < 1.0:
            raise ValueError(f"train_fraction must be in (0, 1); got {self.train_fraction}")
        if self.threshold < 0.0:
            raise ValueError(f"threshold must be non-negative; got {self.threshold}")
        if self.max_iter < 1:
            raise ValueError(f"max_iter must be >= 1; got {self.max_iter}")


# ---------------------------------------------------------------------------
# Feature builders
# ---------------------------------------------------------------------------

def per_axis_feature_names(cfg: FitConfig) -> tuple[str, ...]:
    """Return the per-axis feature names in the order Φ expects them."""
    if cfg.include_bias:
        return PER_AXIS_FEATURES_WITH_BIAS
    return PER_AXIS_FEATURES_NO_BIAS


def per_axis_features(x: np.ndarray, u: np.ndarray, cfg: FitConfig) -> np.ndarray:
    """Build the per-axis polynomial feature matrix Φ ∈ R^(N × n_features).

    Columns: ``[1?, x, u, x^2, x*u, u^2]``. The bias column is included
    iff ``cfg.include_bias``. ``x`` and ``u`` must be 1-D arrays of equal
    length. Output dtype is float64.
    """
    x = np.asarray(x, dtype=np.float64).reshape(-1)
    u = np.asarray(u, dtype=np.float64).reshape(-1)
    if x.shape != u.shape:
        raise ValueError(f"x and u must have the same shape; got {x.shape} vs {u.shape}")
    cols = [x, u, x * x, x * u, u * u]
    if cfg.include_bias:
        cols = [np.ones_like(x), *cols]
    return np.column_stack(cols)


def joint_features(X: np.ndarray) -> np.ndarray:
    """Build the joint polynomial feature matrix Φ ∈ R^(N × 27) from a 6-vector input.

    ``X`` must be ``(N, 6)`` with columns ordered as ``JOINT_INPUT_NAMES``.
    Output is degree-2 polynomial in the 6 columns, no constant term, with
    quadratic entries enumerated in upper-triangular ``(i, j)`` order to
    match ``JOINT_FEATURE_NAMES``.
    """
    X = np.asarray(X, dtype=np.float64)
    if X.ndim != 2 or X.shape[1] != 6:
        raise ValueError(f"X must be (N, 6); got {X.shape}")
    cols: list[np.ndarray] = [X[:, i] for i in range(6)]
    for i in range(6):
        for j in range(i, 6):
            cols.append(X[:, i] * X[:, j])
    return np.column_stack(cols)


# ---------------------------------------------------------------------------
# Train / test split
# ---------------------------------------------------------------------------

def _train_test_split(n: int, cfg: FitConfig) -> tuple[np.ndarray, np.ndarray]:
    """Return (train_idx, test_idx) for an array of length ``n``.

    Deterministic. With ``seed != 0`` shuffles with the given seed; with
    ``seed == 0`` uses the first ``train_fraction * n`` samples as
    train (no shuffle).
    """
    n_train = max(int(cfg.train_fraction * n), 2)
    n_train = min(n_train, n - 1)  # leave at least 1 for test
    if cfg.seed == 0:
        idx = np.arange(n)
    else:
        rng = np.random.RandomState(cfg.seed)
        idx = rng.permutation(n)
    return idx[:n_train], idx[n_train:]


# ---------------------------------------------------------------------------
# Sparse regression
# ---------------------------------------------------------------------------

def _stlsq(
    Phi: np.ndarray,
    y: np.ndarray,
    threshold: float,
    max_iter: int,
) -> np.ndarray:
    """Sequential Thresholded Least Squares (STLSQ).

    Iteratively: 1) OLS on the kept columns, 2) zero out coefs whose
    |coef| < threshold, 3) refit on the surviving columns. Stops when
    the support is stable or ``max_iter`` is reached.

    Returns the (n_features,) coefficient vector. Coefs in dropped
    columns are returned as 0 (not NaN).
    """
    n_features = Phi.shape[1]
    keep = np.ones(n_features, dtype=bool)
    coef = np.zeros(n_features, dtype=np.float64)
    for _ in range(max_iter):
        if not keep.any():
            return coef
        A = Phi[:, keep]
        c, *_ = np.linalg.lstsq(A, y, rcond=None)
        full = np.zeros(n_features, dtype=np.float64)
        full[keep] = c
        new_keep = np.abs(full) >= threshold
        if np.array_equal(new_keep, keep):
            coef = full
            break
        keep = new_keep
        coef = full
    # Final refit on the converged support.
    if keep.any():
        c, *_ = np.linalg.lstsq(Phi[:, keep], y, rcond=None)
        full = np.zeros(n_features, dtype=np.float64)
        full[keep] = c
        coef = full
    return coef


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    *,
    n_active_terms: int,
    n_total_terms: int,
    library: str,
) -> dict:
    """Standard regression metric bundle.

    Returns a dict with keys from ``METRIC_NAMES``. ``NRMSE`` is
    RMSE normalised by the range ``max(y_true) - min(y_true)`` so it
    is comparable across axes with different scales. If the range is
    zero (degenerate target) NRMSE is reported as 0.
    """
    y_true = np.asarray(y_true, dtype=np.float64).reshape(-1)
    y_pred = np.asarray(y_pred, dtype=np.float64).reshape(-1)
    err = y_true - y_pred
    ss_res = float(np.sum(err ** 2))
    mse = float(np.mean(err ** 2))
    rmse = float(np.sqrt(mse))
    mae = float(np.mean(np.abs(err)))
    y_range = float(np.max(y_true) - np.min(y_true))
    if y_range == 0.0:
        nrmse = 0.0
        r2 = 1.0
    else:
        nrmse = rmse / y_range
        ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
        r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0.0 else 1.0
    return {
        "r2": r2,
        "mse": mse,
        "rmse": rmse,
        "mae": mae,
        "nrmse": nrmse,
        "n_active_terms": int(n_active_terms),
        "n_total_terms": int(n_total_terms),
        "library": library,
    }


def _metric_split(split: str) -> str:
    """Return the metric key for a train/test split. e.g. ``"train" -> "r2_train"``."""
    # split is the literal "train" or "test"; metric names follow that pattern.
    return split  # metric dict uses suffixes like r2_train / r2_test below


def _bundle_split_metrics(
    train_metrics: dict,
    test_metrics: dict,
    *,
    n_active: int,
    n_total: int,
    library: str,
) -> dict:
    """Merge train/test metrics into one flat dict keyed by ``METRIC_NAMES``."""
    out = {}
    for src, suffix in [(train_metrics, "train"), (test_metrics, "test")]:
        out[f"r2_{suffix}"] = src["r2"]
        out[f"mse_{suffix}"] = src["mse"]
        out[f"rmse_{suffix}"] = src["rmse"]
        out[f"mae_{suffix}"] = src["mae"]
        out[f"nrmse_{suffix}"] = src["nrmse"]
    out["n_active_terms"] = n_active
    out["n_total_terms"] = n_total
    out["library"] = library
    return out


# ---------------------------------------------------------------------------
# Fit entry points
# ---------------------------------------------------------------------------

def _ols(Phi: np.ndarray, y: np.ndarray) -> np.ndarray:
    c, *_ = np.linalg.lstsq(Phi, y, rcond=None)
    return c


def per_axis_fit(
    t: np.ndarray,
    x: np.ndarray,
    u: np.ndarray,
    *,
    cfg: FitConfig | None = None,
    feature_mask: Sequence[bool] | None = None,
    label: str = "",
) -> dict:
    """Fit one axis with the polynomial library.

    Parameters
    ----------
    t, x, u
        Time, plant state, control input. ``x`` and ``u`` are 1-D;
        ``t`` is used only for the test-set header — the fit itself is
        stateless. Caller is responsible for finite values.
    cfg
        ``FitConfig``; default is the module's recommended defaults.
    feature_mask
        Optional boolean mask over the full feature list; True = keep.
        If given, only the kept columns enter the OLS. Useful for the
        interactive toggle UI: dropping a feature column is equivalent
        to refitting with that column masked out.
    label
        Free-form label (e.g. "roll"); stored in the result.

    Returns
    -------
    dict
        - ``label``
        - ``feature_names`` : list[str] matching the kept features
        - ``coefs`` : np.ndarray shape ``(n_kept,)``
        - ``t`` : original time grid
        - ``y_true`` : measured ``dx``
        - ``y_pred_train`` / ``y_pred_test``
        - ``metrics`` : flat dict keyed by ``METRIC_NAMES``
        - ``train_idx`` / ``test_idx`` : int arrays into ``t``
        - ``library`` : ``"polynomial_per_axis"``
    - ``feature_mask`` : the mask that was used (full or trimmed)
    """
    if cfg is None:
        cfg = FitConfig()
    x = np.asarray(x, dtype=np.float64).reshape(-1)
    u = np.asarray(u, dtype=np.float64).reshape(-1)
    t = np.asarray(t, dtype=np.float64).reshape(-1)
    n = x.shape[0]
    if u.shape[0] != n or t.shape[0] != n:
        raise ValueError(f"t, x, u must have matching lengths; got {t.shape}/{x.shape}/{u.shape}")

    dx = _central_diff(x, t)
    full_names = list(per_axis_feature_names(cfg))
    Phi = per_axis_features(x, u, cfg)
    n_features = Phi.shape[1]
    if feature_mask is None:
        mask = np.ones(n_features, dtype=bool)
    else:
        mask = np.asarray(feature_mask, dtype=bool)
        if mask.shape != (n_features,):
            raise ValueError(
                f"feature_mask length {mask.shape} does not match n_features {n_features}"
            )
    if not mask.any():
        raise ValueError("feature_mask has no True columns; nothing to fit")

    train_idx, test_idx = _train_test_split(n, cfg)
    y_full = dx
    Phi_kept = Phi[:, mask]
    # ``kept_names`` is just for downstream debugging / display; the
    # ``feature_names`` returned in the result is the full-length list
    # so it always aligns with ``coefs`` (which has zero entries for
    # masked-out features).
    _ = [name for keep, name in zip(mask, full_names) if keep]

    coef_full = np.zeros(n_features, dtype=np.float64)
    coef_kept = _stlsq(
        Phi_kept[train_idx], y_full[train_idx], cfg.threshold, cfg.max_iter
    )
    coef_full[mask] = coef_kept

    y_pred = Phi @ coef_full
    y_pred_train = y_pred[train_idx]
    y_pred_test = y_pred[test_idx] if len(test_idx) > 0 else y_pred_train

    n_active = int(np.sum(np.abs(coef_full) > 0.0))
    train_m = compute_metrics(
        y_full[train_idx], y_pred_train,
        n_active_terms=n_active, n_total_terms=n_features, library="polynomial_per_axis",
    )
    test_m = compute_metrics(
        y_full[test_idx], y_pred_test,
        n_active_terms=n_active, n_total_terms=n_features, library="polynomial_per_axis",
    )
    metrics = _bundle_split_metrics(
        train_m, test_m, n_active=n_active,
        n_total=n_features, library="polynomial_per_axis",
    )
    return {
        "label": label,
        "feature_names": full_names,
        "feature_mask": mask,
        "coefs": coef_full,
        "t": t,
        "y_true": y_full,
        "y_pred": y_pred,
        "y_pred_train": y_pred_train,
        "y_pred_test": y_pred_test,
        "train_idx": train_idx,
        "test_idx": test_idx,
        "metrics": metrics,
        "library": "polynomial_per_axis",
    }


def joint_fit(
    per_axis_data: Mapping[str, tuple[np.ndarray, np.ndarray, np.ndarray]],
    *,
    cfg: FitConfig | None = None,
    feature_mask: Sequence[bool] | None = None,
) -> dict:
    """Fit a cross-axis polynomial model on a 6-state ``[x_r, x_p, x_y, u_r, u_p, u_y]``.

    Parameters
    ----------
    per_axis_data
        Mapping ``axis -> (t, x, u)``. All three axes must be present
        and have aligned (or alignable) time grids. The function
        resamples onto the shortest common grid using linear
        interpolation.
    cfg
        ``FitConfig``; defaults are the same as the per-axis case.
    feature_mask
        Optional mask over ``JOINT_FEATURE_NAMES`` (27 features).

    Returns
    -------
    dict
        - ``feature_names`` : list[str] matching the kept joint features
        - ``coefs`` : np.ndarray shape ``(n_kept, 3)`` — one column per
          output ``[dx_roll, dx_pitch, dx_yaw]``
        - ``t`` : aligned time grid
        - ``y_true`` : np.ndarray shape ``(N, 3)``
        - ``y_pred`` : np.ndarray shape ``(N, 3)``
        - ``metrics_per_axis`` : dict keyed by ``"roll" / "pitch" / "yaw"``
          with the same flat metric shape as ``per_axis_fit``
        - ``train_idx`` / ``test_idx``
        - ``library`` : ``"polynomial_joint"``
    """
    if cfg is None:
        cfg = FitConfig()
    required = ("roll", "pitch", "yaw")
    for ax in required:
        if ax not in per_axis_data:
            raise ValueError(f"joint_fit requires '{ax}' in per_axis_data; missing")

    aligned = _align_axes(per_axis_data)
    t = aligned["t"]
    n = t.shape[0]

    # 6-vector: [x_r, x_p, x_y, u_r, u_p, u_y]
    X = np.column_stack([aligned[f"x_{ax}"] for ax in required] +
                        [aligned[f"u_{ax}"] for ax in required])
    Y = np.column_stack([aligned[f"dx_{ax}"] for ax in required])

    Phi = joint_features(X)
    n_features = Phi.shape[1]
    if feature_mask is None:
        mask = np.ones(n_features, dtype=bool)
    else:
        mask = np.asarray(feature_mask, dtype=bool)
        if mask.shape != (n_features,):
            raise ValueError(
                f"feature_mask length {mask.shape} does not match n_features {n_features}"
            )
    if not mask.any():
        raise ValueError("feature_mask has no True columns; nothing to fit")

    train_idx, test_idx = _train_test_split(n, cfg)
    Phi_kept = Phi[:, mask]
    # Return full feature_names so it always aligns with coefs.shape[0].
    # The mask is also returned so callers can iterate just the kept
    # columns if they want.
    coefs = np.zeros((n_features, 3), dtype=np.float64)
    for j in range(3):
        c_j = _stlsq(Phi_kept[train_idx], Y[train_idx, j], cfg.threshold, cfg.max_iter)
        coefs[mask, j] = c_j

    y_pred = Phi @ coefs  # (N, 3)
    metrics_per_axis: dict[str, dict] = {}
    for j, ax in enumerate(required):
        n_active = int(np.sum(np.abs(coefs[:, j]) > 0.0))
        train_m = compute_metrics(
            Y[train_idx, j], y_pred[train_idx, j],
            n_active_terms=n_active, n_total_terms=n_features,
            library="polynomial_joint",
        )
        if len(test_idx) > 0:
            test_m = compute_metrics(
                Y[test_idx, j], y_pred[test_idx, j],
                n_active_terms=n_active, n_total_terms=n_features,
                library="polynomial_joint",
            )
        else:
            test_m = train_m
        metrics_per_axis[ax] = _bundle_split_metrics(
            train_m, test_m,
            n_active=n_active, n_total=n_features,
            library="polynomial_joint",
        )

    return {
        "feature_names": list(JOINT_FEATURE_NAMES),
        "feature_mask": mask,
        "coefs": coefs,
        "t": t,
        "y_true": Y,
        "y_pred": y_pred,
        "y_pred_train": y_pred[train_idx],
        "y_pred_test": y_pred[test_idx] if len(test_idx) > 0 else y_pred[train_idx],
        "train_idx": train_idx,
        "test_idx": test_idx,
        "metrics_per_axis": metrics_per_axis,
        "library": "polynomial_joint",
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _central_diff(x: np.ndarray, t: np.ndarray) -> np.ndarray:
    """Central-difference derivative ``(x[k+1] - x[k-1]) / (2*dt)``.

    Endpoints use one-sided differences. Output has the same shape as
    ``x``. Assumes uniform spacing; falls back to per-step ``dt[k]`` if
    spacing is non-uniform.
    """
    x = np.asarray(x, dtype=np.float64).reshape(-1)
    t = np.asarray(t, dtype=np.float64).reshape(-1)
    n = x.shape[0]
    if n < 2:
        return np.zeros_like(x)
    if n == 2:
        dt = t[1] - t[0]
        if dt == 0:
            return np.zeros_like(x)
        return np.full_like(x, (x[1] - x[0]) / dt)
    dx = np.empty_like(x)
    # Endpoints — one-sided
    dt0 = t[1] - t[0]
    dtn = t[-1] - t[-2]
    dx[0] = (x[1] - x[0]) / dt0 if dt0 != 0 else 0.0
    dx[-1] = (x[-1] - x[-2]) / dtn if dtn != 0 else 0.0
    # Interior — central
    dt_fwd = t[2:] - t[1:-1]
    dt_bwd = t[1:-1] - t[:-2]
    dt = dt_fwd + dt_bwd  # = t[2:] - t[:-2]
    safe = dt != 0
    dx[1:-1] = np.where(
        safe,
        (x[2:] - x[:-2]) / np.where(safe, dt, 1.0),
        0.0,
    )
    return dx


def _align_axes(
    per_axis_data: Mapping[str, tuple[np.ndarray, np.ndarray, np.ndarray]],
) -> dict:
    """Resample all axes onto a common time grid (the shortest common span).

    Returns a dict with keys ``"t", "x_<axis>", "u_<axis>", "dx_<axis>"`` for
    each axis. Linear interpolation; NaN if a sample falls outside the
    source axis's time range (which we clip to the common interior).
    """
    axes = list(per_axis_data.keys())
    if not axes:
        raise ValueError("per_axis_data is empty")

    # Common interior: from max(starts) to min(ends)
    starts = [per_axis_data[a][0][0] for a in axes]
    ends = [per_axis_data[a][0][-1] for a in axes]
    t_start = max(starts)
    t_end = min(ends)
    if t_start >= t_end:
        raise ValueError(
            f"axes do not overlap in time (t_start={t_start}, t_end={t_end})"
        )

    # Use the shortest axis's sampling as the common dt to avoid
    # synthesising fake resolution.
    n_samples = min(per_axis_data[a][0].shape[0] for a in axes)
    t_common = np.linspace(t_start, t_end, n_samples)

    out: dict[str, np.ndarray] = {"t": t_common}
    for ax in axes:
        t_src, x_src, u_src = per_axis_data[ax]
        x_resampled = np.interp(t_common, t_src, x_src)
        u_resampled = np.interp(t_common, t_src, u_src)
        dx_resampled = _central_diff(x_resampled, t_common)
        out[f"x_{ax}"] = x_resampled
        out[f"u_{ax}"] = u_resampled
        out[f"dx_{ax}"] = dx_resampled
    return out
