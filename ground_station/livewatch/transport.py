"""Read-only livewatch transport seam for SWD and the UART5 long-range link.

The seam is the host-side producer of the future ``uart5_address_subscription_cmd``
spec. Both transports expose only block-read paths; neither halts, resets, writes
core memory, arms, nor spins motors. The wireless CMSIS-DAP transport preserves
``connect_mode=attach`` / ``target_override=cortex_m`` / ``resume_on_disconnect=False``.

Pinned UART5 wire contract (host <-> FC):

* Host -> FC request frame (firmware-side spec pins the form):
  ``0xCC 0xDE | 0x20 | LEN_HI LEN_LO (BE) | MAX_NUM_BASIS``, payload of LEN bytes,
  trailer CRC8 XOR. PDB: ``0x20`` is a placeholder command ID; the firmware-side
  spec may renumber it, and the host constant updates with it. The payload is a
  packed list of scalar-request tuples, one per resolved symbol:
  ``address:uint32 LE | size:uint16 LE``. ``size`` MUST be in ``{1, 2, 4}`` so the
  firmware-side validator in HANDOFF §5 item 1 accepts every request without
  raising a contiguous-region exception. ``MAX_NUM_BASIS`` carries the tuple
  count. The host sends this request ONCE per ``sample()`` call.
* FC -> host reply frame:
  ``0xAA 0xBB | 0x07 | LEN_HI LEN_LO (BE) | MAX_NUM_BASIS``, payload of LEN bytes,
  trailer CRC8 XOR (mirrors IF-02's XOR-CRC8 since 0x07 is read-only observation,
  not Frame C's CRC16). Each tuple is ``address:uint32 LE | size:uint16 LE |
  value:size bytes``. The firmware produces one tuple per scalar request and the
  host reassembles them into the contiguous regions that ``build_plan`` produced.
* FC -> host error-reply frame (``0x7F``):
  ``0xAA 0xBB | 0x7F | LEN_HI LEN_LO (BE) | MAX_NUM_BASIS``, payload of LEN bytes
  (UTF-8 NUL-terminated string, <= 240 bytes), trailer CRC8 XOR. Surfaced by
  ``_wait_for_frame`` as a ``LiveTransportError`` carrying the decoded message
  (e.g. ``"E:bad addr"``); the host does not treat 0x7F as a fatal disconnect.

UART5 never falls back to SWD: a missing or malformed reply raises
``LiveTransportError``. The contract above is the only one this transport expects.
"""
from __future__ import annotations

import struct
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from .manifest import CostModel

if TYPE_CHECKING:
    from .reader import Plan


# Subscription data frames: 0x09 + slot, one per slot. They use a CRC16-CCITT
# trailer where the control-plane frames use a single XOR byte.
STREAM_DATA_FRAMES = frozenset(range(0x09, 0x0D))


def crc16_ccitt(data: bytes) -> int:
    """XModem parameters: poly 0x1021, init 0x0000, no reflection, no final XOR.

    Same as Frame C's checksum and ``Crc16Ccitt`` in ``API/subscribe.c``.
    """
    crc = 0
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def pop_frame(rx: bytearray) -> tuple[int, int, bytes] | None:
    """Pop one complete ``0xAA 0xBB`` frame off ``rx``, consuming its bytes.

    Returns ``(frame_type, byte5, payload)`` or ``None`` when no whole frame is
    buffered yet. ``byte5`` is the envelope's sixth byte, whose meaning is
    per-frame: tuple count for 0x07, range count for 0x08, sequence number for
    0x09. Frames whose CRC fails are dropped and the scan continues, so a
    corrupted frame costs one frame rather than resynchronising the stream.

    Module-level (not a method) because the 0x21 streaming path in
    ``stream.py`` decodes the same envelope from a different serial port.
    """
    while True:
        sync = rx.find(b"\xAA\xBB")
        if sync < 0:
            if len(rx) > 1:
                del rx[:-1]
            return None
        if sync:
            del rx[:sync]
        if len(rx) < 6:
            return None
        frame_type = rx[2]
        length = (rx[3] << 8) | rx[4]
        crc16_framed = frame_type == 0x06 or frame_type in STREAM_DATA_FRAMES
        total = 6 + length + (2 if crc16_framed else 1)
        if len(rx) < total:
            return None
        raw = bytes(rx[:total])
        del rx[:total]
        if frame_type == 0x06:
            continue  # Frame C is decoded by serial_bridge, not here
        if crc16_framed:
            # Subscription data frames carry CRC16-CCITT: they ARE the recorded
            # dataset, and an XOR checksum cannot see a byte transposition.
            if crc16_ccitt(raw[2:-2]) != int.from_bytes(raw[-2:], "big"):
                continue
            return frame_type, raw[5], raw[6:-2]
        crc = 0
        for byte in raw[2:-1]:
            crc ^= byte
        if crc != raw[-1]:
            continue
        return frame_type, raw[5], raw[6:-1]


class LiveTransportError(RuntimeError):
    """A transport could not establish or complete a livewatch read."""


class LiveTransport(ABC):
    """Uniform read-only block-sampling transport used by ``LiveReader``."""

    name: str
    cost_model: CostModel
    gap_merge_bytes: int = 48

    @abstractmethod
    def connect(self) -> "LiveTransport":
        pass

    @abstractmethod
    def close(self) -> None:
        pass

    @abstractmethod
    def sample(self, plan: "Plan") -> list[bytes]:
        pass

    def calibrate(self, reader, plan: "Plan", n: int = 15):
        from .manifest import calibrate
        return calibrate(reader, plan, cost_model=self.cost_model, n=n)


class SwdCmsisDap(LiveTransport):
    """Safe pyOCD attach-mode RAM reader; never halts, resets, or writes."""

    name = "swd"
    cost_model = CostModel(
        2.2, 0.031, "swd-cmsis-dap",
        "rounded up from 2026-07-26 wireless CMSIS-DAP measurements",
    )
    gap_merge_bytes = 48

    def __init__(self):
        self._session = None
        self.target = None

    def connect(self) -> "SwdCmsisDap":
        from pyocd.core.helpers import ConnectHelper
        self._session = ConnectHelper.session_with_chosen_probe(
            options={
                "target_override": "cortex_m",
                "connect_mode": "attach",
                "resume_on_disconnect": False,
            }
        )
        if self._session is None:
            raise LiveTransportError(
                "no CMSIS-DAP probe found (is Keil holding it? close its debug session)"
            )
        self._session.open()
        self.target = self._session.target
        return self

    def close(self) -> None:
        if self._session is not None:
            self._session.close()
        self._session = None
        self.target = None

    def sample(self, plan: "Plan") -> list[bytes]:
        if self.target is None:
            raise LiveTransportError("swd-read: not connected")
        return [bytes(self.target.read_memory_block8(r.start, r.size))
                for r in plan.regions]


class Uart5LongRange(LiveTransport):
    """Full-duplex 115200-baud UART5 observer with a request-then-reassemble read."""

    name = "uart5"
    cost_model = CostModel(
        8.0, 0.31, "uart5-long-range",
        "estimated, not measured; conservative 115200-baud model until calibrate() runs",
    )
    gap_merge_bytes = 26

    _REPLY_FRAME = 0x07
    _ERROR_FRAME = 0x7F
    _SUBSCRIBE_CMD = 0x20
    _QUIET_DRAIN_S = 0.05

    def __init__(self, port: str, baud: int = 115200, timeout: float = 1.0,
                 serial_factory=None):
        if not port or str(port).upper() == "AUTO":
            raise LiveTransportError(
                "uart5-read: set a manual --uart5-port or livewatch_uart5_port"
            )
        self.port = str(port)
        self.baud = int(baud)
        self.timeout = float(timeout)
        self._serial_factory = serial_factory
        self._serial = None
        self._rx = bytearray()

    def connect(self) -> "Uart5LongRange":
        factory = self._serial_factory
        if factory is None:
            import serial
            factory = serial.Serial
        try:
            self._serial = factory(self.port, self.baud, timeout=0.05)
            self._drain_quiet_window()
        except LiveTransportError:
            self.close()
            raise
        except Exception as exc:
            self.close()
            raise LiveTransportError(f"uart5-read: could not open {self.port}: {exc}") from exc
        return self

    def close(self) -> None:
        serial_obj = self._serial
        self._serial = None
        self._rx.clear()
        if serial_obj is not None:
            serial_obj.close()

    def _drain_quiet_window(self) -> None:
        """Discard any in-flight bytes from a previous operator session.

        Read-only observation: no command frame is sent on connect. The transport
        waits for the next 0x07 reply to arrive naturally during a sample() call.
        """
        deadline = time.monotonic() + self._QUIET_DRAIN_S
        while time.monotonic() < deadline:
            waiting = getattr(self._serial, "in_waiting", 0)
            chunk = self._serial.read(waiting or 1)
            if not chunk:
                time.sleep(0.005)
        if self._rx:
            self._rx.clear()

    def sample(self, plan: "Plan") -> list[bytes]:
        if self._serial is None:
            raise LiveTransportError("uart5-read: not connected")
        request = self._build_request(plan.symbols)
        try:
            self._serial.write(request)
        except Exception as exc:
            raise LiveTransportError(f"uart5-read: write failed: {exc}") from exc
        _, count, payload = self._wait_for_frame(
            self._REPLY_FRAME,
            "firmware subscription reply (uart5_address_subscription_cmd has not shipped)",
        )
        scalars = self._decode_tuples(payload, count)
        return self._reassemble(plan, scalars)

    def _build_request(self, symbols) -> bytes:
        """Build the pinned subscribe request frame for the resolved symbols.

        See module docstring. ``MAX_NUM_BASIS`` carries the resolved tuple count.
        The size for each symbol is constrained to ``{1, 2, 4}`` per the
        firmware-side validator; the host walker raises ``LiveTransportError``
        if any symbol violates that, rather than letting the firmware silently
        reject an out-of-range scalar.
        """
        tuples = []
        for sym in symbols:
            if sym.size not in (1, 2, 4):
                raise LiveTransportError(
                    f"uart5-read: symbol {sym.name!r} size {sym.size} not in {{1,2,4}}"
                )
            tuples.append(struct.pack("<IH", sym.address, sym.size))
        payload = b"".join(tuples)
        count = len(tuples)
        body = bytes((self._SUBSCRIBE_CMD, (len(payload) >> 8) & 0xFF,
                      len(payload) & 0xFF, count)) + payload
        crc = 0
        for byte in body:
            crc ^= byte
        # Request frame header is 0xCC 0xDE (extended IF-01 prefix); reply
        # frames (parsed by _pop_frame) still key on 0xAA 0xBB. The two
        # headers are deliberately distinct so a stray request byte in the
        # reply stream cannot be mis-decoded as the start of a reply.
        return b"\xCC\xDE" + body + bytes((crc,))

    @staticmethod
    def _reassemble(plan, scalars: dict[tuple[int, int], bytes]) -> list[bytes]:
        """Reassemble per-symbol scalar tuples into the coalesced ``plan.regions``.

        The firmware replies with one tuple per requested ``(address, size)``.
        ``build_plan`` may coalesce adjacent scalars into a larger region, so the
        host has to reconstruct the original region bytes by walking the
        plan's symbols in order and concatenating their scalar values.
        """
        blocks = []
        for region in plan.regions:
            buf = bytearray()
            for sym in plan.symbols:
                if region.start <= sym.address < region.end:
                    key = (sym.address, sym.size)
                    if key not in scalars:
                        raise LiveTransportError(
                            f"uart5-read: reply omitted {sym.name!r} "
                            f"at 0x{sym.address:08X}+{sym.size}"
                        )
                    buf.extend(scalars[key])
            if not buf:
                raise LiveTransportError(
                    f"uart5-read: empty region 0x{region.start:08X}+{region.size}"
                )
            blocks.append(bytes(buf))
        return blocks

    def _wait_for_frame(self, wanted_type: int, purpose: str) -> tuple[int, int, bytes]:
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            frame = self._pop_frame()
            if frame is not None:
                frame_type, _count, payload = frame
                if frame_type == wanted_type:
                    return frame
                if frame_type == self._ERROR_FRAME:
                    msg = payload.decode("utf-8", errors="replace").rstrip("\x00")
                    raise LiveTransportError(f"uart5-read: firmware error: {msg}")
                continue
            waiting = getattr(self._serial, "in_waiting", 0)
            chunk = self._serial.read(waiting or 1)
            if chunk:
                self._rx.extend(chunk)
        raise LiveTransportError(f"uart5-read: no reply on {purpose}")

    def _pop_frame(self) -> tuple[int, int, bytes] | None:
        return pop_frame(self._rx)

    @staticmethod
    def _decode_tuples(payload: bytes, count: int) -> dict[tuple[int, int], bytes]:
        out = {}
        offset = 0
        for _ in range(count):
            if offset + 6 > len(payload):
                raise LiveTransportError("uart5-read: truncated address+value tuple")
            address, size = struct.unpack_from("<IH", payload, offset)
            offset += 6
            end = offset + size
            if end > len(payload):
                raise LiveTransportError("uart5-read: truncated tuple value")
            out[(address, size)] = payload[offset:end]
            offset = end
        if offset != len(payload):
            raise LiveTransportError("uart5-read: trailing bytes after address+value tuples")
        return out
