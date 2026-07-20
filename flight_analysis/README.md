# Flight Analysis Framework

State-of-the-art performance and stability analysis for UAV flight logs.

## Installation

```bash
pip install -e .
```

## Quick Start

```bash
python -m flight_analysis.cli analyze ground_station/logs/flight_1784538359.csv
```

## Architecture

See `docs/ADR-0007-flight-analysis-framework.md` for design decisions.

## Testing

```bash
pytest tests/ -v
```
