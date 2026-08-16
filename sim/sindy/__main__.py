"""CLI for the SINDy pipeline (legacy).

The previous ``view`` subcommand rendered a static HTML viewer; that has
been superseded by the interactive Streamlit dashboard at
:mod:`sim.dashboard`. Run it with::

    .venv/bin/python -m streamlit run sim/dashboard/app.py

The CLI is kept here so existing scripts that invoke ``python -m sim.sindy``
do not fail with a confusing ImportError; the command now points the
operator at the dashboard.
"""
from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sim.sindy",
        description=(
            "Legacy CLI entrypoint. The interactive dashboard is now the "
            "recommended way to explore a log file:\n"
            "    .venv/bin/python -m streamlit run sim/dashboard/app.py"
        ),
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("view", help="(removed — use the Streamlit dashboard)").set_defaults(
        func=lambda _a: _print_redirect(),
    )

    if argv is not None and len(argv) == 0:
        argv = ["--help"]
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    return int(args.func(args))


def _print_redirect() -> int:
    print(
        "The static `view` HTML renderer has been replaced by the\n"
        "interactive Streamlit dashboard. Run:\n"
        "    .venv/bin/python -m streamlit run sim/dashboard/app.py\n",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())