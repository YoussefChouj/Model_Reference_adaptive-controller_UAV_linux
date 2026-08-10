"""TDD — sim/delay.py ActuatorDelayBuffer.

Pins the transport-delay FIFO semantics lifted out of ``sim/plant._AxisSim``
(ADR-0012 D6). The wrapper must be a drop-in replacement for the inline
buffer: ``N == round(T/dt)`` of integer-sample delay, first N reads after
``reset()`` return 0, then the value enqueued N ticks ago.

Tests:

*   basic delay (N=1, N=3)
*   N=0 passthrough (no FIFO)
*   reset restores zero-output behaviour
*   ring-buffer wrap-around beyond N samples
*   multi-axis independence (one buffer, separate FIFOs per axis)
*   vector inputs (np.ndarray) and scalar broadcasts
*   sample-rate semantics: dt doesn't enter the buffer, only N does
"""
import numpy as np
import pytest

from sim.delay import ActuatorDelayBuffer


# ----------------------------------------------------------------------
# Basic delay
# ----------------------------------------------------------------------
def test_n_one_delays_one_tick():
    buf = ActuatorDelayBuffer(N=1)
    # First read returns 0 (initial FIFO state), then the previous input.
    assert float(buf.step(1.0)[0]) == 0.0
    assert float(buf.step(2.0)[0]) == 1.0
    assert float(buf.step(3.0)[0]) == 2.0


def test_n_three_delays_three_ticks():
    # Same semantics as the prior inline ``_AxisSim.buf`` for ``IdentifiedPlant``
    # roll (T = 0.015 s, dt = 0.005 s -> N = 3): first three reads return 0.
    buf = ActuatorDelayBuffer(N=3)
    out = [float(buf.step(float(i + 1))[0]) for i in range(6)]
    assert out == [0.0, 0.0, 0.0, 1.0, 2.0, 3.0]


# ----------------------------------------------------------------------
# N == 0 passthrough
# ----------------------------------------------------------------------
def test_n_zero_is_pure_passthrough():
    buf = ActuatorDelayBuffer(N=0)
    for v in [0.5, -1.0, 3.14]:
        assert float(buf.step(v)[0]) == pytest.approx(v)
    # No FIFO state carried; reset is a no-op for N=0 (still passthrough).
    buf.reset()
    assert float(buf.step(7.0)[0]) == pytest.approx(7.0)


# ----------------------------------------------------------------------
# Reset
# ----------------------------------------------------------------------
def test_reset_restores_zero_initial_state():
    buf = ActuatorDelayBuffer(N=2)
    buf.step(1.0)
    buf.step(2.0)
    buf.step(3.0)
    # Buffer now has [2, 3] in slots; next read should be 2.
    assert float(buf.step(0.0)[0]) == pytest.approx(2.0)
    buf.reset()
    # After reset, the first two reads return 0 again.
    assert float(buf.step(0.0)[0]) == 0.0
    assert float(buf.step(0.0)[0]) == 0.0


# ----------------------------------------------------------------------
# Ring buffer wrap-around
# ----------------------------------------------------------------------
def test_wrap_around_preserves_oldest_first_semantics():
    # Fill N=4, then keep stepping; the oldest value in the FIFO is the
    # one returned, exactly as in the inline list-based implementation.
    buf = ActuatorDelayBuffer(N=4)
    seq = list(range(1, 11))   # 10 inputs, N=4 FIFO
    out = [float(buf.step(v)[0]) for v in seq]
    # First 4 reads return 0 (initial state), then the first 4 inputs,
    # then the next 2 inputs.
    assert out == [0.0, 0.0, 0.0, 0.0, 1, 2, 3, 4, 5, 6]


def test_long_run_recovers_value_exactly():
    # Running far past N reproduces the value N ticks ago.
    buf = ActuatorDelayBuffer(N=5)
    rng = np.random.default_rng(0)
    seq = list(rng.standard_normal(50))
    for v in seq:
        buf.step(float(v))
    # After 50 steps with N=5, the buffer holds seq[45:50]; the next 5
    # reads return them in FIFO order.
    out = np.array([float(buf.step(0.0)[0]) for _ in range(5)])
    np.testing.assert_allclose(out, seq[45:50], rtol=1e-12, atol=1e-15)


# ----------------------------------------------------------------------
# Multi-axis independence
# ----------------------------------------------------------------------
def test_multi_axis_independence():
    buf = ActuatorDelayBuffer(N=2, n_axes=3)
    # Three independent FIFO columns, each delay N=2.
    out = buf.step(np.array([1.0, 10.0, 100.0]))
    np.testing.assert_array_equal(out, np.array([0.0, 0.0, 0.0]))
    out = buf.step(np.array([2.0, 20.0, 200.0]))
    np.testing.assert_array_equal(out, np.array([0.0, 0.0, 0.0]))
    # Third read: first input per axis.
    out = buf.step(np.array([3.0, 30.0, 300.0]))
    np.testing.assert_array_equal(out, np.array([1.0, 10.0, 100.0]))


def test_scalar_broadcasts_across_axes():
    buf = ActuatorDelayBuffer(N=1, n_axes=4)
    assert np.allclose(buf.step(5.0), np.array([0.0, 0.0, 0.0, 0.0]))
    out = buf.step(7.0)
    np.testing.assert_array_equal(out, np.array([5.0, 5.0, 5.0, 5.0]))


def test_wrong_shape_input_raises():
    buf = ActuatorDelayBuffer(N=1, n_axes=3)
    with pytest.raises(ValueError):
        buf.step(np.array([1.0, 2.0]))   # 2 elements, not 3


# ----------------------------------------------------------------------
# Sample-rate behaviour
# ----------------------------------------------------------------------
def test_buffer_is_independent_of_dt():
    # The buffer's N is the only delay knob; dt is the caller's concern.
    # Constructing two buffers with the same N must produce the same
    # output sequence regardless of how the caller chooses to drive them.
    def drive(buf, seq):
        return [float(buf.step(v)[0]) for v in seq]

    seq = [1.0, 2.0, 3.0, 4.0, 5.0]
    a = drive(ActuatorDelayBuffer(N=3), seq)
    b = drive(ActuatorDelayBuffer(N=3), seq)
    assert a == b == [0.0, 0.0, 0.0, 1.0, 2.0]


def test_n_attribute_exposed():
    buf = ActuatorDelayBuffer(N=7)
    assert buf.N == 7
    assert buf.n_axes == 1
    buf2 = ActuatorDelayBuffer(N=0, n_axes=2)
    assert buf2.N == 0 and buf2.n_axes == 2


def test_negative_n_rejected():
    with pytest.raises(ValueError):
        ActuatorDelayBuffer(N=-1)


def test_parity_with_inline_implementation():
    """Cross-check against the legacy inline FIFO used in _AxisSim.

    The inline implementation is:
        buf = [0.0] * N
        if self.N:
            self.buf.append(u)
            u_eff = self.buf.pop(0)
        else:
            u_eff = u

    For N=3, the same sequence of ``step(u)`` calls must return the same
    delayed values. Bit-exact for the FIFO's first 3*N reads.
    """
    N = 3
    inline_buf = [0.0] * N
    new_buf = ActuatorDelayBuffer(N=N)

    def inline_step(u):
        if N:
            inline_buf.append(u)
            return inline_buf.pop(0)
        return u

    seq = [1.1, 2.2, 3.3, 4.4, 5.5, 6.6, 7.7, 8.8]
    legacy = [inline_step(v) for v in seq]
    new = [float(new_buf.step(v)[0]) for v in seq]
    assert legacy == new