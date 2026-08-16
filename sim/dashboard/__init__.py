"""Research dashboard package — interactive Streamlit UI for fit exploration.

Public surface (deep, small):
- :class:`FitSession`  — one (log, axes, feature_mask) → many plots.
- :func:`get_adapter`  — file-extension → :class:`LogAdapter`.

Everything else (loading, fitting, plotting, KPI math) sits inside these
modules' implementations. Adding a new log format means writing one
:class:`LogAdapter` subclass; adding a new plot means extending
:class:`FitSession` with one method.
"""

from sim.dashboard.session import FitSession, AxisFit
from sim.dashboard.adapters import LogAdapter, get_adapter, list_supported_exts

__all__ = [
    "FitSession",
    "AxisFit",
    "LogAdapter",
    "get_adapter",
    "list_supported_exts",
]