"""Command-line front end for livewatch.

  python -m ground_station.livewatch names [--filter STR]
  python -m ground_station.livewatch fields <symbol>
  python -m ground_station.livewatch groups
  python -m ground_station.livewatch read  <name|group:...> [names...]
  python -m ground_station.livewatch watch <name|group:...> [names...] [--hz N] [--secs S] [--csv FILE]

`names`/`fields`/`groups` need no hardware (pure DWARF). `read`/`watch` open a
read-only attach session to the running target.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from .registry import Registry
from .symbols import SymbolResolver

_DEFAULT_ELF = Path(__file__).resolve().parents[2] / "OBJ" / "JX_FLY.axf"


def _resolver(args) -> SymbolResolver:
    return SymbolResolver(args.elf)


def cmd_names(args):
    r = _resolver(args)
    flt = (args.filter or "").lower()
    for n in r.names():
        if flt in n.lower():
            print(n)


def cmd_fields(args):
    r = _resolver(args)
    for f in r.fields_of(args.symbol):
        print(f)


def cmd_groups(args):
    reg = Registry()
    for g in reg.group_names():
        print(f"{g:14s} {reg.doc(g)}")
        for v in reg.vars(g):
            print(f"    {v}")


def _expand(args) -> list[str]:
    return Registry().expand(args.names)


def cmd_read(args):
    from .reader import LiveReader
    names = _expand(args)
    with LiveReader(args.elf) as lr:
        plan = lr.plan(names)
        print(f"# {len(plan.regions)} region(s) / {len(names)} vars")
        row = lr.sample(plan)
        for n in names:
            v = row[n]
            print(f"{n:22s} {_fmt(v)}")


def cmd_watch(args):
    from .reader import LiveReader
    names = _expand(args)
    writer = None
    fh = None
    with LiveReader(args.elf) as lr:
        try:
            for row in lr.stream(names, hz=args.hz, duration=args.secs):
                if args.csv and writer is None:
                    fh = open(args.csv, "w", newline="")
                    writer = csv.DictWriter(fh, fieldnames=list(row))
                    writer.writeheader()
                if writer:
                    writer.writerow(row)
                line = "  ".join(f"{k}={_fmt(v)}" for k, v in row.items())
                print(line)
        except KeyboardInterrupt:
            print("\n# stopped", file=sys.stderr)
        finally:
            if fh:
                fh.close()
                print(f"# wrote {args.csv}", file=sys.stderr)


def _fmt(v):
    if isinstance(v, float):
        return f"{v:+.5g}"
    if isinstance(v, (bytes, bytearray)):
        return f"<{len(v)}B>"
    return str(v)


def build_parser():
    p = argparse.ArgumentParser(prog="livewatch", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--elf", default=str(_DEFAULT_ELF), help="firmware ELF (default OBJ/JX_FLY.axf)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("names", help="list resolvable base symbols")
    sp.add_argument("--filter", help="substring filter (case-insensitive)")
    sp.set_defaults(func=cmd_names)

    sp = sub.add_parser("fields", help="list members/elements under a symbol")
    sp.add_argument("symbol")
    sp.set_defaults(func=cmd_fields)

    sp = sub.add_parser("groups", help="list registry watch groups")
    sp.set_defaults(func=cmd_groups)

    sp = sub.add_parser("read", help="one-shot read (needs hardware)")
    sp.add_argument("names", nargs="+", help="paths and/or group:<name> tokens")
    sp.set_defaults(func=cmd_read)

    sp = sub.add_parser("watch", help="stream at N Hz (needs hardware)")
    sp.add_argument("names", nargs="+", help="paths and/or group:<name> tokens")
    sp.add_argument("--hz", type=float, default=20.0)
    sp.add_argument("--secs", type=float, default=None, help="stop after S seconds")
    sp.add_argument("--csv", help="also log samples to CSV")
    sp.set_defaults(func=cmd_watch)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
