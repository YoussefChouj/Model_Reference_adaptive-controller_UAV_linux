"""Integer-sample transport-delay buffer (ADR-0012 D6).

Lifted out of ``sim/plant._AxisSim`` so every 6-DOF plant and the closed-loop
runner share one well-tested delay primitive. The semantics match the prior
inline implementation bit-for-bit:

*   ``step(u)`` returns the value enqueued ``N`` ticks ago.
*   On the first ``N`` ticks after construction / ``reset()`` the buffer
    returns 0 (initial state).
*   ``N == 0`` is a pure passthrough.

The transport delay ``T`` (seconds) for an axis plant is converted to samples
via ``N = round(T / dt)``.  Identified plants (docs/sysid_results.md):

    roll  : T = 0.015 s -> N = 3  (at dt = 0.005 s)
    pitch : T = 0.012 s -> N = 2
    yaw   : T = 0      -> N = 0

ADR-0012 D6 makes this mandatory on every 6-DOF plant used for prior learning
because weights learned on a delay-free plant are systematically over-confident.

The buffer accepts either scalar ``float`` inputs or 1-D ``np.ndarray`` inputs.
For ndarray input the same N-sample FIFO is applied independently per element;
each axis of an ActuatorDelayBuffer instance is a separate FIFO so multi-axis
plants (e.g. ``IdentifiedPlant``) compose without sharing state across axes.
"""
from __future__ import annotations

from typing import Union

import numpy as np

DelayInput = Union[float, np.ndarray]


class ActuatorDelayBuffer:
    """Integer-sample FIFO delay wrapper.

    Parameters
    ----------
    N : int
        Number of ticks to delay the input. ``N == 0`` is a passthrough.
        Negative ``N`` is rejected at construction.
    n_axes : int
        Number of independent FIFOs to allocate. The plant interface is
        per-axis, so each axis gets its own FIFO. ``n_axes == 1`` covers
        scalar use and the per-axis callsite inside ``_AxisSim``.
    dtype : np.dtype, optional
        Numeric dtype for the FIFO contents. Defaults to ``float64`` to
        match the inline implementation's plain Python floats and to give
        bit-identical output against the legacy code.
    """

    def __init__(self, N: int, n_axes: int = 1, *, dtype=np.float64):
        if N < 0:
            raise ValueError(f"N must be >= 0, got {N}")
        if n_axes < 1:
            raise ValueError(f"n_axes must be >= 1, got {n_axes}")
        self.N = int(N)
        self.n_axes = int(n_axes)
        self._buf = np.zeros((self.N, self.n_axes), dtype=dtype)
        self._write_idx = 0
        self._count = 0  # ticks seen since construction/reset, capped at N

    def reset(self) -> None:
        """Restore zero-state FIFOs (first N reads return 0)."""
        self._buf.fill(0.0)
        self._write_idx = 0
        self._count = 0

    def _coerce(self, u: DelayInput) -> np.ndarray:
        """Coerce ``u`` to shape ``(n_axes,)``. Scalar broadcasts."""
        a = np.asarray(u, dtype=self._buf.dtype)
        if a.ndim == 0:
            a = np.full(self.n_axes, float(a), dtype=self._buf.dtype)
        elif a.shape != (self.n_axes,):
            raise ValueError(
                f"input shape {a.shape} does not match n_axes={self.n_axes}"
            )
        return a

    def step(self, u: DelayInput) -> np.ndarray:
        """Advance one sample; return the value enqueued N ticks ago.

        On the first ``N`` ticks after ``__init__``/``reset()``, returns 0
        for every axis (initial FIFO state). When ``N == 0`` returns ``u``
        unchanged.
        """
        u_arr = self._coerce(u)
        if self.N == 0:
            return u_arr.copy()
        # Read position: the oldest sample currently in the FIFO. For a
        # circular buffer of length N that has seen `min(_count, N)` writes,
        # the oldest sample is at the write cursor when the buffer is full,
        # otherwise at index 0 (initial zeros).
        if self._count < self.N:
            # Buffer not yet full; initial zeros precede the first N writes.
            out = np.zeros(self.n_axes, dtype=self._buf.dtype)
            self._count += 1
        else:
            out = self._buf[self._write_idx].copy()
        # Write the current input at the write cursor; advance the cursor.
        self._buf[self._write_idx] = u_arr
        self._write_idx = (self._write_idx + 1) % self.N
        return out

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"ActuatorDelayBuffer(N={self.N}, n_axes={self.n_axes})"