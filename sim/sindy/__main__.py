"""``python -m sim.sindy view <ulog> [<out_html>] [--fit] [--title TITLE] [--downsample N]``

Subcommand-driven CLI for the SINDy module. Currently only ``view`` is
implemented.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _cmd_view(args: argparse.Namespace) -> int:
    from sim.sindy.viewer import view_ulog

    out_html = args.out_html
    if out_html is None:
        out_html = (
            Path("sim/sindy/viewer_output")
            / (Path(args.ulog).stem + ".html")
        )
    out_html = Path(out_html)
    meta = view_ulog(
        args.ulog,
        out_html,
        fit=args.fit,
        downsamples_to=args.downsample,
        title=args.title,
    )
    print(json.dumps(meta, indent=2, default=str))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m sim.sindy")
    sub = parser.add_subparsers(dest="command", required=True)

    p_view = sub.add_parser("view", help="Render a Plotly HTML viewer for a PX4 ulog")
    p_view.add_argument("ulog", help="Path to a PX4 .ulog file")
    p_view.add_argument("out_html", nargs="?", default=None,
                        help="Destination HTML path (default: sim/sindy/viewer_output/<basename>.html)")
    p_view.add_argument("--fit", action="store_true",
                        help="Also run preprocess_px4 + linear SINDy on roll axis")
    p_view.add_argument("--title", default=None,
                        help="Optional HTML title override")
    p_view.add_argument("--downsample", type=int, default=5000,
                        help="Max samples per trace after downsample (default 5000)")
    p_view.set_defaults(func=_cmd_view)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
