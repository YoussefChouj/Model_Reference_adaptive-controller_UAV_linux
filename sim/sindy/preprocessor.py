"""Prepare a FlightDataset for SINDy: derivatives, outlier removal, resample, normalise.

SINDy requires:
- Uniformly-spaced time grid
- Finite, real-valued data
- Time derivatives of the state variables

The preprocessor handles all three.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from sim.sindy.flight_loader import FlightDataset


@dataclass
class PreprocessedDataset:
    """SINDy-ready time-series data.

    Attributes
    ----------
    t : np.ndarray
        Uniformly-spaced time grid (seconds).
    X : np.ndarray
        Feature matrix, shape ``(n_samples, 3)`` with columns ``[e, x, xm]``.
        ``e`` and ``xm`` come directly from the telemetry;
        ``x = xm - e`` is the reconstructed plant state.

        This matrix is what SINDy models: ``d(X)/dt = f(X)``.
        The adaptive law dynamics are ``ė = -A_m * e + Theta^T * Phi``,
        so SINDy on ``[e, x, xm]`` recovers the error-dynamics structure.
    dXdt : np.ndarray
        Time derivatives of ``X``, same shape.
    feature_names : list[str]
        Column labels for ``X``.
    axis : str
        Axis the source data came from.
    meta : dict
        Forwarded from ``FlightDataset.meta``.
    normalise_stats : dict
        Per-column ``(mean, std)`` used to invert the normalisation.
        Present only when ``normalise=True``.
    """
    t: np.ndarray
    X: np.ndarray
    dXdt: np.ndarray
    feature_names: list[str]
    axis: str
    meta: dict = field(default_factory=dict)
    normalise_stats: Optional[dict[str, tuple[float, float]]] = None

    @property
    def n_samples(self) -> int:
        return self.X.shape[0]

    @property
    def n_features(self) -> int:
        return self.X.shape[1]


def preprocess(
    dataset: FlightDataset,
    *,
    normalise: bool = False,
    outlier_threshold: float = 10.0,
    dt: Optional[float] = None,
) -> PreprocessedDataset:
    """Prepare a ``FlightDataset`` for SINDy.

    Steps, in order:

    1. **Sort by time** — ensures monotonic ``t``.
    2. **Outlier removal** — replace ``|value| > threshold × std(value)`` with
       ``NaN``, then interpolate.
    3. **Resample** — uniform grid at ``dt`` (median dt if not given).
    4. **Derivative** — second-order central difference:
       ``dX/dt ≈ (X[i+1] - X[i-1]) / (t[i+1] - t[i-1])``.
       Endpoints use forward / backward difference.
    5. **Normalise** (optional) — z-score each column; store stats for inversion.

    Parameters
    ----------
    dataset
        Source ``FlightDataset``.
    normalise
        Apply z-score normalisation to ``X``.
    outlier_threshold
        Replace ``|value| > threshold × std(value)`` with ``NaN``.
        Set to ``0`` to disable outlier removal.
    dt
        Uniform time step. Inferred from median dt if not provided.

    Returns
    -------
    PreprocessedDataset
        ``feature_names`` are ``["bias", "x", "xm", "u_nom"]``.
        These map to the 6-basis regressor as::

            bias  → slot 0
            x     → slots 1 (rate) + 2 (drag via x*tanh(x))
            xm    → slot 5
            u_nom → slot 4

        Slots 3 (cross-coupling) is axis-dependent and not included here;
        it is handled separately in the SINDy fitting step.
    """
    t = dataset.t.copy()
    e = dataset.e.copy()
    xm = dataset.xm.copy()
    u_nom = dataset.u_nom.copy()
    x = dataset.x.copy()
    u = dataset.u.copy()

    # --- 1. Sort ---
    order = np.argsort(t)
    t = t[order]
    e = e[order]
    xm = xm[order]
    u_nom = u_nom[order]
    x = x[order]
    u = u[order]

    # --- 2. Outlier removal ---
    if outlier_threshold > 0:
        for arr in (e, xm, u_nom, x, u):
            std = float(np.std(arr[np.isfinite(arr)]))
            if std > 0:
                bad = np.abs(arr) > outlier_threshold * std
                arr[bad] = float("nan")

        # Interpolate NaN values.
        for arr in (e, xm, u_nom, x, u):
            _interpolate_inplace(arr)

    # --- 3. Resample to uniform grid ---
    if dt is None:
        if len(t) < 2:
            dt = 0.01
        else:
            dt = float(np.median(np.diff(t)))

    t_min, t_max = float(t[0]), float(t[-1])
    n = max(2, int(round((t_max - t_min) / dt)) + 1)
    t_grid = np.linspace(t_min, t_max, n)

    def _resample(signal: np.ndarray) -> np.ndarray:
        return np.interp(t_grid, t, signal)

    e_rs = _resample(e)
    xm_rs = _resample(xm)
    u_nom_rs = _resample(u_nom)
    x_rs = _resample(x)

    # --- 4. Build feature matrix ---
    # Two matrices are needed:
    #   X_e: features for SINDy on error dynamics: ė = f(e, xm, x)
    #   X_phi: analytical regressor vector (for mapping active terms → Θ slots)
    bias = np.ones(n)
    x_tanh = x_rs * np.tanh(x_rs)
    # SINDy feature matrix: [e, x, xm] — the three signals whose dynamics SINDy fits
    # u_nom is treated as exogenous (known input) — excluded from the dynamics model.
    X = np.column_stack([e_rs, x_rs, xm_rs])
    feature_names = ["e", "x", "xm"]

    # --- 5. Derivatives ---
    dXdt = _central_derivative(X, t_grid)

    # --- 6. Normalise ---
    norm_stats: Optional[dict[str, tuple[float, float]]] = None
    if normalise:
        norm_stats = {}
        X_out = np.empty_like(X)
        for i, name in enumerate(feature_names):
            col = X[:, i]
            finite = col[np.isfinite(col)]
            if len(finite) < 2:
                mean, std = 0.0, 1.0
            else:
                mean, std = float(np.mean(finite)), float(np.std(finite))
            std = std if std > 0 else 1.0
            norm_stats[name] = (mean, std)
            X_out[:, i] = (col - mean) / std
        X = X_out

    return PreprocessedDataset(
        t=t_grid,
        X=X,
        dXdt=dXdt,
        feature_names=feature_names,
        axis=dataset.axis,
        meta=dataset.meta.copy(),
        normalise_stats=norm_stats,
    )


def preprocess_px4(
    dataset: "FlightDataset",
    *,
    normalise: bool = False,
    dt: Optional[float] = None,
) -> "PreprocessedDataset":
    """PX4-only preprocessor that builds a **single-feature** matrix ``[x]``.

    PX4 ``.ulg`` files do not contain ``mrac_state.e`` or ``mrac_state.xm``,
    so the canonical ``preprocess`` (which builds ``[e, x, xm]``) cannot
    produce a finite derivative — the central difference goes ``NaN`` on
    NaN columns.

    For plant-state-only SINDy on PX4 data we want a clean fit on ``x``
    alone: the caller passes ``fit_sindy(X, dt, library="linear")`` and
    the ``IdentityLibrary`` maps directly to the single column.

    Parameters
    ----------
    dataset
        Source ``FlightDataset``. ``x`` must be finite; ``e`` / ``xm`` may
        be NaN (they are ignored).
    normalise
        Apply z-score normalisation to ``X``.
    dt
        Uniform time step. Inferred from median dt if not provided.

    Returns
    -------
    PreprocessedDataset
        ``X`` shape ``(N, 1)``, ``feature_names = ["x"]``.
    """
    t = dataset.t.copy()
    x = dataset.x.copy()

    # --- 1. Sort ---
    order = np.argsort(t)
    t = t[order]
    x = x[order]

    # --- 2. Outlier removal ---
    if np.any(~np.isfinite(x)):
        # Replace any non-finite values with linear interpolation in time
        # so the central difference produces finite derivatives.
        valid = np.isfinite(x)
        if np.any(valid):
            x[~valid] = np.interp(
                t[~valid], t[valid], x[valid],
                left=float(x[valid][0]), right=float(x[valid][-1]),
            )
        else:
            x[:] = 0.0

    # --- 3. Resample to uniform grid ---
    if dt is None:
        if len(t) < 2:
            dt = 0.01
        else:
            dt = float(np.median(np.diff(t)))

    t_min, t_max = float(t[0]), float(t[-1])
    n = max(2, int(round((t_max - t_min) / dt)) + 1)
    t_grid = np.linspace(t_min, t_max, n)
    x_rs = np.interp(t_grid, t, x)

    # --- 4. Build feature matrix ---
    X = x_rs.reshape(-1, 1)
    feature_names = ["x"]

    # --- 5. Derivatives ---
    dXdt = _central_derivative(X, t_grid)

    # --- 6. Normalise ---
    norm_stats: Optional[dict[str, tuple[float, float]]] = None
    if normalise:
        norm_stats = {}
        X_out = np.empty_like(X)
        col = X[:, 0]
        finite = col[np.isfinite(col)]
        if len(finite) < 2:
            mean, std = 0.0, 1.0
        else:
            mean, std = float(np.mean(finite)), float(np.std(finite))
        std = std if std > 0 else 1.0
        norm_stats["x"] = (mean, std)
        X_out[:, 0] = (col - mean) / std
        X = X_out

    return PreprocessedDataset(
        t=t_grid,
        X=X,
        dXdt=dXdt,
        feature_names=feature_names,
        axis=dataset.axis,
        meta=dataset.meta.copy(),
        normalise_stats=norm_stats,
    )


def _interpolate_inplace(arr: np.ndarray) -> None:
    """Replace NaN in ``arr`` with linearly interpolated values."""
    n = len(arr)
    valid = np.isfinite(arr)
    if np.all(valid):
        return
    if not np.any(valid):
        arr[:] = 0.0
        return

    x = np.arange(n)
    arr[:] = np.interp(x, x[valid], arr[valid])


def _central_derivative(X: np.ndarray, t: np.ndarray) -> np.ndarray:
    """Second-order central difference. Endpoints use forward/backward diff."""
    n = X.shape[0]
    dXdt = np.empty_like(X)

    for i in range(n):
        if i == 0:
            dt = float(t[1] - t[0])
            dXdt[0] = (X[1] - X[0]) / dt if dt != 0 else np.zeros(X.shape[1])
        elif i == n - 1:
            dt = float(t[-1] - t[-2])
            dXdt[-1] = (X[-1] - X[-2]) / dt if dt != 0 else np.zeros(X.shape[1])
        else:
            half_dt = float(t[i + 1] - t[i])
            dXdt[i] = (X[i + 1] - X[i - 1]) / (2.0 * half_dt) if half_dt != 0 else np.zeros(X.shape[1])

    return dXdt
