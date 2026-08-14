"""SINDy prior library pipeline.

Two SINDy uses:
1. SINDy on adaptive law — tells which Θ slots are active for a scenario class.
   Output: Prior objects seeded closer to the converged solution.
2. SINDy on plant — discovers dynamics terms; signals when to extend the basis.
   Output: basis extension recommendations.

Data flows:
    stream_log CSV  → flight_loader → preprocessor → fitter → prior_generator
    PX4 .ulog file → adapters.ulog → preprocessor → fitter
                                                           ↓
                                               priors/<name>.json → sim validation
"""
from sim.sindy.flight_loader import FlightDataset, load_stream_log_csv
from sim.sindy.preprocessor import PreprocessedDataset, preprocess, preprocess_px4
from sim.sindy.adapters.ulog import load_ulog
from sim.sindy.viewer import view_ulog

__all__ = [
    "FlightDataset",
    "load_stream_log_csv",
    "PreprocessedDataset",
    "preprocess",
    "preprocess_px4",
    "load_ulog",
    "view_ulog",
]
