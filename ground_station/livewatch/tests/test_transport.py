"""Offline tests for the livewatch transport abstraction."""
from argparse import Namespace

import pytest

from ground_station.livewatch.cli import _transport
from ground_station.livewatch.reader import Plan, Region
from ground_station.livewatch.symbols import Symbol
from ground_station.livewatch.transport import (
    LiveTransportError, SwdCmsisDap, Uart5LongRange,
)


def _frame(frame_type, payload=b"", count=0):
    body = bytes((frame_type, len(payload) >> 8, len(payload) & 0xFF, count)) + payload
    crc = 0
    for byte in body:
        crc ^= byte
    return b"\xAA\xBB" + body + bytes((crc,))


class FakeSerial:
    def __init__(self, port, baud, timeout=0.05, reply=b""):
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.rx = bytearray(reply)
        self.writes = []
        self.closed = False

    @property
    def in_waiting(self):
        return len(self.rx)

    def write(self, data):
        self.writes.append(bytes(data))
        return len(data)

    def read(self, size=1):
        out = bytes(self.rx[:size])
        del self.rx[:size]
        return out

    def close(self):
        self.closed = True


def test_cli_transport_defaults_to_swd():
    args = Namespace(transport="swd", uart5_port=None, uart5_baud=None)
    assert isinstance(_transport(args), SwdCmsisDap)


def test_cli_uart5_constructs_selected_transport():
    args = Namespace(transport="uart5", uart5_port="COM42", uart5_baud=230400)
    transport = _transport(args)
    assert isinstance(transport, Uart5LongRange)
    assert transport.port == "COM42"
    assert transport.baud == 230400


def test_transport_cost_models_are_distinct_and_label_uart_estimate():
    swd = SwdCmsisDap.cost_model.describe()
    uart = Uart5LongRange.cost_model.describe()
    assert swd != uart
    assert "estimated, not measured" in uart


def test_uart5_request_pinned_format():
    """Verifies the host->FC request frame is built exactly as the docstring pins.

    The frame is NOT sent on connect anymore -- connect() is silent. The frame
    is sent on each sample() call. We construct the request directly via
    _build_request and assert the byte layout is what's pinned in the module
    docstring: 0xCC 0xDE | 0x20 | LEN_HI LEN_LO (BE) | MAX_NUM_BASIS, payload
    of packed (address:uint32 LE | size:uint16 LE) tuples, trailer CRC8 XOR.
    """
    sym_a = Symbol("s_ekf.x[3]", 0x20000100, 4, "f")
    sym_b = Symbol("s_ekf.x[4]", 0x20000104, 4, "f")
    transport = Uart5LongRange("COM42", serial_factory=lambda *a, **kw: FakeSerial("COM42", 115200))
    frame = transport._build_request([sym_a, sym_b])
    assert frame[:2] == b"\xCC\xDE"
    assert frame[2] == 0x20
    length = (frame[3] << 8) | frame[4]
    assert length == 2 * 6
    assert frame[5] == 2  # MAX_NUM_BASIS = 2
    payload = frame[6:6 + length]
    assert payload == (
        sym_a.address.to_bytes(4, "little") + sym_a.size.to_bytes(2, "little") +
        sym_b.address.to_bytes(4, "little") + sym_b.size.to_bytes(2, "little")
    )
    crc = 0
    for byte in frame[2:-1]:
        crc ^= byte
    assert frame[-1] == crc


def test_uart5_sample_reassembles_per_symbol_into_regions():
    """FC replies with one tuple per requested scalar; the host reassembles.

    The 4 floats below (16 B) would coalesce into a single 16 B region in
    build_plan. The firmware-only-safe reply is one tuple per scalar, so the
    host has to walk the plan's symbols and concatenate the four scalar values
    back into the 16 B region block.
    """
    base = 0x20000100
    values = [b"\x00\x00\x80\x3F", b"\x00\x00\x00\x40",
              b"\x00\x00\x40\x40", b"\x00\x00\x80\x40"]  # 1.0, 2.0, 3.0, 4.0
    tuples = b"".join(
        (base + 4 * i).to_bytes(4, "little") + (4).to_bytes(2, "little") + v
        for i, v in enumerate(values)
    )
    fake = FakeSerial("COM42", 115200, reply=b"")
    transport = Uart5LongRange(
        "COM42", timeout=0.5, serial_factory=lambda *a, **kw: fake).connect()
    try:
        # Inject the 0x07 reply AFTER the connect() drain so the transport
        # sees it on the next sample() call.
        fake.rx.extend(_frame(0x07, tuples, 4))
        # Hand-build a Plan with one 16 B region and four 4 B symbols so the
        # host reassembly is forced.
        symbols = [Symbol(f"s_ekf.x[{i}]", base + 4 * i, 4, "f") for i in range(4)]
        plan = Plan(symbols=symbols, regions=[Region(base, 16)])
        blocks = transport.sample(plan)
        assert blocks == [b"".join(values)]
    finally:
        transport.close()


def test_uart5_sample_decodes_single_scalar_region():
    """Single 4-byte region requested; the FC replies with one tuple and the
    host returns the 4-byte block. Verifies the path still works for the
    simple, non-coalesced case (one symbol, one region).
    """
    address = 0x20000100
    value = b"\x00\x00\xA0\x3F"
    payload = address.to_bytes(4, "little") + len(value).to_bytes(2, "little") + value
    fake = FakeSerial("COM42", 115200, reply=b"")
    transport = Uart5LongRange(
        "COM42", timeout=0.5, serial_factory=lambda *a, **kw: fake).connect()
    try:
        fake.rx.extend(_frame(0x07, payload, 1))
        sym = Symbol("s_ekf.x[3]", address, 4, "f")
        plan = Plan(symbols=[sym], regions=[Region(address, 4)])
        assert transport.sample(plan) == [value]
    finally:
        transport.close()


def test_uart5_timeout_fails_loud_without_swd_fallback(monkeypatch):
    """No SWD construction when the UART5 transport times out.

    The no-fallback contract requires that the transport itself AND every
    higher callback layer (LiveReader, dashboard _livelog_check_budget) never
    substitute SwdCmsisDap() on a UART5 failure. We wrap SwdCmsisDap with a
    construction counter so a hidden fallback would be visible.
    """
    constructions = []
    real_swd = SwdCmsisDap

    class CountingSwd(real_swd):
        def __init__(self, *a, **kw):
            constructions.append(1)
            super().__init__(*a, **kw)

    monkeypatch.setattr(
        "ground_station.livewatch.transport.SwdCmsisDap", CountingSwd)
    fake = FakeSerial("COM42", 115200, reply=b"")
    transport = Uart5LongRange(
        "COM42", timeout=0.001, serial_factory=lambda *a, **kw: fake).connect()
    try:
        with pytest.raises(LiveTransportError, match="no reply"):
            transport.sample(Plan(symbols=[], regions=[]))
        assert constructions == []
    finally:
        transport.close()


def test_uart5_requires_manual_port():
    with pytest.raises(LiveTransportError, match="manual"):
        Uart5LongRange("")


def test_uart5_error_reply_surfaced():
    """A 0x7F error reply from the FC is surfaced as LiveTransportError.

    The firmware emits a 0x7F frame on validation failure (e.g. an address
    outside SRAM/CCM, an unaligned read, or a CRC mismatch). The host must
    not silently drop it; it must raise LiveTransportError with the payload
    string visible so the operator can see the FC's reason.
    """
    err_msg = b"E:bad addr\x00"
    frame = _frame(0x7F, err_msg, 0)
    fake = FakeSerial("COM42", 115200, reply=b"")
    transport = Uart5LongRange(
        "COM42", timeout=0.5, serial_factory=lambda *a, **kw: fake).connect()
    try:
        # Inject the 0x7F frame AFTER connect() drain so the transport sees it
        # on the next _wait_for_frame() call (matching the existing sample tests).
        fake.rx.extend(frame)
        with pytest.raises(LiveTransportError, match="E:bad addr"):
            transport._wait_for_frame(transport._REPLY_FRAME, "test")
    finally:
        transport.close()
