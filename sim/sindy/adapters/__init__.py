# sim/sindy/adapters — format adapters for non-stream_log telemetry.
#
# Each adapter implements:
#
#     def load(path: str | Path) -> FlightDataset | None:
#         """Return FlightDataset if format matches, None otherwise."""
#
# Format is detected by extension in the parent loader.

from sim.sindy.adapters.ulog import load_ulog

__all__ = ["load_ulog"]
