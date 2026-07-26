"""livewatch — non-intrusive live variable watch for the STM32F407 flight controller.

Reads RAM off the running target through a selected read-only transport and resolves
any variable, struct field, or array element to its address *by name* from the
firmware's DWARF debug info.

Layers:
  symbols.py  - DWARF-backed name -> (address, ctype) resolver (offline, no hardware)
  reader.py   - safe attach-mode pyOCD reader with coalesced block transfers
  registry.py - curated groups of important variables to watch
  cli.py      - `python -m ground_station.livewatch ...`

Safety contract (enforced in reader.py): attach connect, read-only, cortex_m
override, resume_on_disconnect=False. No write/halt/reset path exists in this
package. Reading RAM cannot change the ARM flag, so motors stay off.
"""
from .symbols import SymbolResolver, Symbol
from .reader import LiveReader
from .transport import (
    LiveTransport, LiveTransportError, SwdCmsisDap, Uart5LongRange,
)

__all__ = [
    "SymbolResolver", "Symbol", "LiveReader", "LiveTransport",
    "LiveTransportError", "SwdCmsisDap", "Uart5LongRange",
]
