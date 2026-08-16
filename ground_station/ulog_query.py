"""CLI for DWARF-aware ulog querying.

Usage::

    ulog_query dump    <file.ulg> [--elf <path>] [--topic <name>]
    ulog_query at      <file.ulg> --at <seconds> [--elf <path>]
    ulog_query between <file.ulg> --t0 <s> --t1 <s> [--topic <name>]
    ulog_query fields  <file.ulg> [--elf <path>]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ground_station.ulog_reader import ULogReader


def cmd_dump(args: argparse.Namespace) -> None:
    reader = ULogReader(args.file, args.elf)
    topics = [args.topic] if args.topic else reader.topics
    for topic in topics:
        print(f"=== {topic} ===")
        df = reader.topic(topic)
        print(df.head(20).to_string())
        print()


def cmd_at(args: argparse.Namespace) -> None:
    reader = ULogReader(args.file, args.elf)
    snap = reader.at(args.at)
    for topic, fields in snap.items():
        print(f"=== {topic} ===")
        for k, v in fields.items():
            print(f"  {k}: {v}")
        print()


def cmd_between(args: argparse.Namespace) -> None:
    reader = ULogReader(args.file, args.elf)
    topics = [args.topic] if args.topic else reader.topics
    for topic in topics:
        df = reader.between(args.t0, args.t1)[topic]
        print(f"=== {topic} [{args.t0}s–{args.t1}s] ===")
        print(df.to_string())
        print()


def cmd_fields(args: argparse.Namespace) -> None:
    reader = ULogReader(args.file, args.elf)
    results = reader.fields_resolved()
    print(f"{'ULog field':<35} {'DWARF resolved?':<20} {'Address':>12}  {'Size':>6}")
    print("-" * 80)
    for r in results:
        from ground_station.ulog_reader import ResolvedField, UnresolvedField
        if isinstance(r, ResolvedField):
            status = "yes"
            addr = f"0x{r.address:08X}"
            size = str(r.size)
            dw_path = r.dwarf_path
        else:
            status = f"no ({r.reason})"
            addr = "-"
            size = "-"
            dw_path = "-"
        print(f"{r.ulog_field:<35} {status:<20} {addr:>12}  {size:>6}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ulog_query",
                                     description="DWARF-aware PX4 ulog query tool")
    sub = parser.add_subparsers(required=True)

    p = sub.add_parser("dump", help="Print head of every (or one) topic")
    p.add_argument("file", type=Path)
    p.add_argument("--elf", type=Path, default=None)
    p.add_argument("--topic", default=None)
    p.set_defaults(fn=cmd_dump)

    p = sub.add_parser("at", help="Snapshot of every topic at a timestamp")
    p.add_argument("file", type=Path)
    p.add_argument("--at", type=float, required=True, help="Timestamp in seconds")
    p.add_argument("--elf", type=Path, default=None)
    p.set_defaults(fn=cmd_at)

    p = sub.add_parser("between", help="All samples of topic(s) in a time window")
    p.add_argument("file", type=Path)
    p.add_argument("--t0", type=float, required=True, help="Start time in seconds")
    p.add_argument("--t1", type=float, required=True, help="End time in seconds")
    p.add_argument("--topic", default=None)
    p.add_argument("--elf", type=Path, default=None)
    p.set_defaults(fn=cmd_between)

    p = sub.add_parser("fields", help="Show ulog field → DWARF resolution table")
    p.add_argument("file", type=Path)
    p.add_argument("--elf", type=Path, default=None)
    p.set_defaults(fn=cmd_fields)

    args = parser.parse_args(argv)
    try:
        args.fn(args)
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
