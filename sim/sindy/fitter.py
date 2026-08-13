"""SINDy sparse regression using PySINDy 2.x.

Three library options:

- ``"linear"``
    ``[e, x, xm]`` — raw signals, no polynomial expansion.
    3 terms, 3 features. Diagnostic baseline; R² should be poor.

- ``"match_6basis"``
    Polynomial degree-1 on ``[e, x, xm]``: ``[1, e, x, xm]``.
    4 terms, 3 features. Maps to MRAC Θ slots 0–3:
    ``1`` → bias, ``e`` → rate damping, ``x`` → nonlinear drag proxy,
    ``xm`` → reference feedforward. Slots 4–5 (u_nom, cross-coupling)
    are not discoverable from telemetry alone; they come from the MRAC
    analysis step.

- ``"overcomplete"``
    Polynomial degree 1–3 on ``[e, x, xm]``: 20 terms.
    Use this to discover whether a new basis function consistently activates
    across multiple flights. Consistent activation → file an ADR and add
    the term to ``BASIS_DEFAULT``.

Usage::

    from sim.sindy import load_stream_log_csv, preprocess
    from sim.sindy.fitter import fit_sindy

    ds  = load_stream_log_csv("my_flight.csv", axis="roll")
    pp  = preprocess(ds)
    res = fit_sindy(pp.X, dt=pp.t[1]-pp.t[0], library="match_6basis")
    print(res.active_term_names())
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


# Library identifiers.
LIBRARY_LINEAR = "linear"
LIBRARY_MATCH_6BASIS = "match_6basis"
LIBRARY_OVERCOMPLETE = "overcomplete"
LIBRARIES = (LIBRARY_LINEAR, LIBRARY_MATCH_6BASIS, LIBRARY_OVERCOMPLETE)


@dataclass
class SindyResult:
    """Output of a SINDy fit.

    Attributes
    ----------
    coefs : np.ndarray
        Sparse coefficient matrix, shape ``(n_features, n_terms)``.
        Row ``i`` is ``d(X[:,i])/dt = coefs[i] @ Phi``.
    active_terms : np.ndarray
        Boolean mask of which terms are active.
        Shape ``(n_features, n_terms)``.
    feature_names : list[str]
        Names of the features (columns of ``X``): ``["e", "x", "xm"]``.
    term_names : list[str]
        Names of the library terms.
    quality_metrics : dict
        ``r2_train``, ``r2_test``, ``n_active_terms``, ``active_threshold``.
    library_id : str
        Which library was used (``LIBRARY_LINEAR`` etc.).
    """
    coefs: np.ndarray
    active_terms: np.ndarray
    feature_names: list[str]
    term_names: list[str]
    quality_metrics: dict
    library_id: str = field(default="")

    @property
    def n_features(self) -> int:
        return self.coefs.shape[0]

    @property
    def n_terms(self) -> int:
        return self.coefs.shape[1]

    def active_term_names(self) -> list[list[str]]:
        """Per-feature list of active term names."""
        out = []
        for i in range(self.n_features):
            active = [
                self.term_names[j]
                for j in range(self.n_terms)
                if self.active_terms[i, j]
            ]
            out.append(active)
        return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fit_sindy(
    X: np.ndarray,
    dt: float,
    *,
    library: str = LIBRARY_MATCH_6BASIS,
    n_train: float = 0.8,
    random_state: int = 42,
    threshold: float = 0.05,
    max_iter: int = 5000,
) -> SindyResult:
    """Sparse regression against ``d(X)/dt`` using PySINDy.

    Parameters
    ----------
    X
        Feature matrix, shape ``(n_samples, 3)`` with columns ``["e", "x", "xm"]``.
        Produced by ``preprocess(FlightDataset)``.
    dt
        Uniform time step in seconds.
    library
        Candidate library. See module docstring for descriptions.
    n_train
        Fraction of data used for training (rest for test R²).
    random_state
        Seed for the train/test split.
    threshold
        STLSQ sparsity threshold. Higher = sparser model.
    max_iter
        Optimizer max iterations.

    Returns
    -------
    SindyResult

    Raises
    ------
    ValueError
        If ``X`` has fewer than 10 samples or ``dt`` is not positive.
    """
    import pysindy as ps

    if X.ndim != 2:
        raise ValueError(f"X must be 2-D, got shape {X.shape}")
    n_samples, n_features = X.shape
    if n_samples < 10:
        raise ValueError(f"need at least 10 samples, got {n_samples}")
    if dt <= 0:
        raise ValueError(f"dt must be positive, got {dt}")
    if n_features != 3:
        raise ValueError(
            f"X must have 3 columns [e, x, xm]; got {n_features}"
        )

    # Feature names.
    feature_names = ["e", "x", "xm"]

    # Train/test split.
    rng = np.random.RandomState(random_state)
    indices = rng.permutation(n_samples)
    n_train_samples = max(int(n_train * n_samples), 10)
    train_idx = indices[:n_train_samples]
    test_idx = indices[n_train_samples:]

    X_train = X[train_idx]
    X_test = X[test_idx] if len(test_idx) > 0 else X_train[-2:]

    # Compute dX/dt for training.
    dXdt_train = _central_derivative(X_train, dt)

    # Build the SINDy model.
    model = _build_model(library, threshold, max_iter)

    # Fit.
    model.fit(X_train, x_dot=dXdt_train, t=dt)

    # Coefficient matrix: (n_features, n_terms)
    coefs = np.array(model.coefficients())

    # Term names: use canonical names where known, otherwise use pysindy's.
    term_names = _canonical_term_names(library)
    if not term_names:
        term_names = model.get_feature_names()

    # Evaluate quality.
    dXdt_test = (
        _central_derivative(X_test, dt)
        if len(test_idx) > 1
        else dXdt_train[-2:]
    )
    y_pred_train = model.predict(X_train)
    y_pred_test = model.predict(X_test)

    r2_train = _r2(dXdt_train[1:], y_pred_train[1:])
    r2_test = (
        _r2(dXdt_test[1:], y_pred_test[1:])
        if len(test_idx) > 1
        else r2_train
    )

    # Active terms: above a fraction of the coefficient range.
    abs_coefs = np.abs(coefs)
    active_threshold = max(
        float(np.percentile(abs_coefs, 80)) * 0.1,
        threshold * 0.5,
    )
    active_terms = abs_coefs > active_threshold

    quality_metrics = {
        "r2_train": float(r2_train),
        "r2_test": float(r2_test),
        "n_active_terms": int(np.sum(active_terms)),
        "active_threshold": float(active_threshold),
    }

    return SindyResult(
        coefs=coefs,
        active_terms=active_terms,
        feature_names=feature_names,
        term_names=term_names,
        quality_metrics=quality_metrics,
        library_id=library,
    )


# ---------------------------------------------------------------------------
# Library builders
# ---------------------------------------------------------------------------

def _build_model(
    library: str,
    threshold: float,
    max_iter: int,
):
    """Construct a ``pysindy.SINDy`` model with the named library."""
    import pysindy as ps

    if library == LIBRARY_MATCH_6BASIS:
        # Polynomial degree-1 on [e, x, xm]: terms = [1, e, x, xm]
        # Maps to MRAC slots: 1→bias, e→rate, x→drag proxy, xm→ref feedforward
        optimizer = ps.STLSQ(
            threshold=threshold,
            alpha=0.01,
            max_iter=max_iter,
            normalize_columns=False,
        )
        lib = ps.PolynomialLibrary(
            degree=1,
            include_bias=True,
            include_interaction=False,
        )
        return ps.SINDy(feature_library=lib, optimizer=optimizer)

    elif library == LIBRARY_LINEAR:
        # Raw signals: [e, x, xm] — no polynomial expansion.
        # 3 terms, 3 features. Poor R² expected (adaptive law is nonlinear).
        optimizer = ps.STLSQ(
            threshold=0.0,
            alpha=0.0,
            max_iter=max_iter,
            normalize_columns=False,
        )
        lib = ps.IdentityLibrary()
        return ps.SINDy(feature_library=lib, optimizer=optimizer)

    elif library == LIBRARY_OVERCOMPLETE:
        # Polynomial degree 1–3 on [e, x, xm]: 20 terms.
        # Discover any consistently-activated terms that fall outside [1, e, x, xm].
        # These are the signal to extend the MRAC basis.
        optimizer = ps.STLSQ(
            threshold=threshold,
            alpha=0.01,
            max_iter=max_iter,
            normalize_columns=False,
        )
        lib = ps.PolynomialLibrary(
            degree=3,
            include_bias=True,
            include_interaction=True,
        )
        return ps.SINDy(feature_library=lib, optimizer=optimizer)

    else:
        raise ValueError(f"unknown library {library!r}. Options: {LIBRARIES}")


def _canonical_term_names(library: str) -> list[str]:
    """Return canonical term names for each library."""
    if library == LIBRARY_MATCH_6BASIS:
        # [1, e, x, xm] from PolynomialLibrary(degree=1) on [e, x, xm]
        return ["1", "e", "x", "xm"]
    if library == LIBRARY_LINEAR:
        # IdentityLibrary: each feature is its own term
        return ["e", "x", "xm"]
    if library == LIBRARY_OVERCOMPLETE:
        # PolynomialLibrary(degree=3) on [e, x, xm]: 20 terms
        # Names from pysindy: ["1","e","x","xm","e^2","e x","e xm",...]
        return []  # use pysindy's names at runtime
    return []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _central_derivative(X: np.ndarray, dt: float) -> np.ndarray:
    """Second-order central difference for a uniform grid."""
    n = X.shape[0]
    dXdt = np.empty_like(X)
    dXdt[0] = (X[1] - X[0]) / dt
    dXdt[-1] = (X[-1] - X[-2]) / dt
    dXdt[1:-1] = (X[2:] - X[:-2]) / (2.0 * dt)
    return dXdt


def _r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    if ss_tot == 0:
        return 1.0
    return float(1.0 - ss_res / ss_tot)
