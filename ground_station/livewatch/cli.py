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
import struct
import sys
from pathlib import Path

from .patch import SafetyGateError, patch_symbol
from .registry import Registry
from .symbols import SymbolResolver, WritableField
from .transport import LiveTransportError, SwdCmsisDap, Uart5LongRange

_DEFAULT_ELF = Path(__file__).resolve().parents[2] / "OBJ" / "JX_FLY.axf"
_DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config.yaml"


def _resolver(args) -> SymbolResolver:
    return SymbolResolver(args.elf)


def _transport_config() -> dict[str, str]:
    out = {}
    if _DEFAULT_CONFIG.exists():
        for raw in _DEFAULT_CONFIG.read_text(errors="replace").splitlines():
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            out[key.strip()] = value.strip()
    return out


def _transport(args):
    if getattr(args, "transport", "swd") == "uart5":
        cfg = _transport_config()
        port = getattr(args, "uart5_port", None) or cfg.get("livewatch_uart5_port", "")
        baud = getattr(args, "uart5_baud", None) or int(
            cfg.get("livewatch_uart5_baud", 115200))
        return Uart5LongRange(port=port, baud=baud)
    return SwdCmsisDap()


def _live_reader(args):
    from .reader import LiveReader
    return LiveReader(args.elf, transport=_transport(args))


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
    names = _expand(args)
    with _live_reader(args) as lr:
        plan = lr.plan(names)
        print(f"# {len(plan.regions)} region(s) / {len(names)} vars")
        row = lr.sample(plan)
        for n in names:
            v = row[n]
            print(f"{n:22s} {_fmt(v)}")


def cmd_watch(args):
    names = _expand(args)
    writer = None
    fh = None
    with _live_reader(args) as lr:
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


def _SAFETY_MESSAGE() -> str:
    return (
        "\n"
        "livewatch patch — SAFETY GATE\n"
        "===============================\n"
        "This command WRITES to RAM on the running target via SWD.\n"
        "A torn write to a 32-bit variable is not possible on Cortex-M4\n"
        "(ARM AAPCS guarantees atomic 32-bit stores), but the write is\n"
        "irreversible within the running session and WILL be lost on\n"
        "reboot or power-cycle.\n"
        "\n"
        "Always disarm before patching.  The --no-disarm-check flag is\n"
        "logged at WARNING level and should only be used on the bench\n"
        "with props OFF and the operator ready to power-cycle.\n"
    )


def cmd_patch(args):
    import math

    if not args.i_understand:
        print(_SAFETY_MESSAGE(), file=sys.stderr)
        print("ERROR: --i-understand is required.  Exiting.", file=sys.stderr)
        raise SystemExit(2)

    try:
        value = float(args.value)
    except ValueError:
        print(f"ERROR: {args.value!r} is not a valid float", file=sys.stderr)
        raise SystemExit(1)

    if not math.isfinite(value):
        print(f"ERROR: {value} is not a finite float", file=sys.stderr)
        raise SystemExit(1)

    transport = _transport(args)
    with transport:
        try:
            result = patch_symbol(
                elf_path=args.elf,
                symbol_name=args.symbol,
                value=value,
                transport=transport,
                i_understand=True,
                require_disarmed=not args.no_disarm_check,
                halt_for_write=args.halt,
                verify=not args.verify_only,
                dry_run=args.dry_run,
            )
        except SafetyGateError as exc:
            if not args.no_disarm_check:
                print(f"\n[livewatch patch] DISARM GATE BLOCKED\n", file=sys.stderr)
            print(f"ERROR: {exc}", file=sys.stderr)
            raise SystemExit(2)

    # Banner
    mode = "DRY-RUN" if args.dry_run else ("VERIFY ONLY" if args.verify_only else "WRITE")
    banner_lines = [
        "",
        "[livewatch patch] *** LIVE RAM WRITE ***",
        f"  symbol:  {args.symbol}",
        f"  address: 0x{result.address:08X}",
        f"  old:     {struct.unpack('<f', result.old_value.to_bytes(4, 'little'))[0]:.6f}",
        f"  new:     {struct.unpack('<f', result.new_value.to_bytes(4, 'little'))[0]:.6f}",
        f"  mode:    {mode}",
        f"  verify:  {'on' if (not args.verify_only and not args.dry_run) else 'skipped'}",
        f"  gate:    {'DISARMED' if not args.no_disarm_check else 'DISARM_CHECK DISABLED'}",
        f"  duration: {result.duration_ms:.1f} ms",
        "",
    ]
    for line in banner_lines:
        print(line)

    if args.no_disarm_check:
        print("WARNING: --no-disarm-check was set.  Vehicle arm state was NOT verified.",
              file=sys.stderr)

    if result.verified:
        print("[OK] write verified", file=sys.stderr)
    return 0


def cmd_verify(args):
    """Prove OBJ/JX_FLY.axf is the build running on the target before trusting a read."""
    from .reader import LiveReader
    from .verify import compare, flash_segments, plan_samples

    segs = flash_segments(args.elf)
    samples = plan_samples(segs, n=args.chunks)
    print(f"# {len(segs)} flash segment(s), sampling {len(samples)} chunk(s)", file=sys.stderr)
    with LiveReader(args.elf) as lr:
        res = compare(samples, lambda a, n: lr._target.read_memory_block8(a, n))
    print(res.describe())
    return 0 if res.ok else 2


def cmd_freshness(args):
    """Read a field twice with a small delay; report whether the value advanced.

    Catches wireless-bridge staleness. With a USB-wired CMSIS-DAP, every
    monotonically-advancing field (a tick counter, a millisecond clock) will
    change between two reads separated by ~10 ms. With a wireless bridge under
    load, the host may see a cached/stale value and the test fails.

    Exits 0 on fresh, 3 on stale.
    """
    import time
    from .reader import LiveReader

    name = args.field
    delay_ms = args.delay_ms
    n = args.samples
    if n < 2:
        raise SystemExit("freshness needs --samples >= 2")

    with LiveReader(args.elf, transport=_transport(args)) as lr:
        plan = lr.plan([name])
        last = None
        rows = []
        t0 = time.perf_counter()
        for i in range(n):
            sample = lr.sample(plan)[name]
            t = time.perf_counter() - t0
            rows.append((t, sample))
            if i < n - 1:
                time.sleep(delay_ms / 1000.0)
        elapsed = rows[-1][0] - rows[0][0]

    # Report
    print(f"# field={name}  samples={n}  delay_ms={delay_ms}  elapsed={elapsed*1000:.1f} ms")
    for t, v in rows:
        print(f"  t={t*1000:7.1f} ms   value={_fmt(v)}")

    # Freshness test: at least one value must differ across the window
    values = [v for _, v in rows]
    if all(v == values[0] for v in values):
        print("# STALE: every read returned the same value — bridge is caching or the field is frozen")
        return 3
    if args.require_monotonic and all(isinstance(v, (int, float)) for v in values):
        if not all(values[i] <= values[i + 1] for i in range(len(values) - 1)):
            print("# STALE: non-monotonic — possible bridge reorder or duplicated sample")
            return 3
    print("# FRESH: values advanced during the sample window")
    return 0


def cmd_manifests(args):
    from .manifest import ManifestStore
    store = ManifestStore()
    for n in store.names():
        m = store.get(n)
        doc = " ".join(m.doc.split())
        print(f"{n:16s} {m.hz:>5g} Hz  {len(m.vars):>3} vars   {doc[:90]}")


def cmd_transports(args):
    for transport in (SwdCmsisDap(), Uart5LongRange(port="CONFIGURED")):
        print(f"{transport.name:8s} {transport.cost_model.describe()}")


def _manifest_for(args):
    """Either a named manifest or an ad-hoc one built from --vars."""
    from .manifest import ManifestStore
    store = ManifestStore()
    if args.vars:
        return store.adhoc(args.vars, hz=args.hz or 20.0, name=args.name or "adhoc")
    m = store.get(args.manifest)
    if args.hz:
        m.hz = args.hz
    return m


def cmd_budget(args):
    """Feasible sample rate for a manifest. Pure DWARF + cost model, no hardware."""
    from .manifest import feasibility
    from .reader import build_plan
    m = _manifest_for(args)
    transport = _transport(args)
    plan = build_plan(_resolver(args), m.vars, transport.gap_merge_bytes)
    feas = feasibility(plan, cost_model=transport.cost_model)
    print(f"{m.name}: {feas.describe()}")
    if feas.ok_for(m.hz):
        print(f"  requested {m.hz:g} Hz -> OK ({m.hz / feas.max_hz * 100:.0f}% of ceiling)")
    else:
        print(f"  requested {m.hz:g} Hz -> TOO FAST, ceiling is ~{feas.max_hz:.0f} Hz")
    for r in plan.regions:
        print(f"    region 0x{r.start:08X} +{r.size} B")


def cmd_writable(args):
    """List all RAM-writable members under a base name (or all globals if no base given)."""
    r = _resolver(args)
    base = args.base_name if args.base_name else ""
    fields = r.writable_members(base)

    if args.format == "json":
        import json
        out = [
            {
                "name": w.name,
                "address": f"0x{w.address:08X}",
                "c_type": w.c_type,
                "size_bytes": w.size_bytes,
                "parent": w.parent,
            }
            for w in fields
        ]
        print(json.dumps(out, indent=2))
    else:
        print(f"{'name':<45} {'address':>10}  {'c_type':<20} {'size':>5}  parent")
        print("-" * 95)
        for w in fields:
            print(f"{w.name:<45} 0x{w.address:08X}  {w.c_type:<20} {w.size_bytes:>5}  {w.parent}")


def cmd_log(args):
    """Log a manifest to a uniquely named CSV, after checking the rate is real."""
    from .manifest import unique_csv_path, write_meta
    m = _manifest_for(args)
    with _live_reader(args) as lr:
        plan = lr.plan(m.vars)
        feas = lr.transport.calibrate(lr, plan)
        print(f"# {m.name}: {feas.describe()}", file=sys.stderr)

        hz = m.hz
        if not feas.ok_for(hz):
            if args.clamp:
                hz = feas.max_hz
                print(f"# requested {m.hz:g} Hz exceeds the ceiling; clamped to {hz:.0f} Hz",
                      file=sys.stderr)
            else:
                print(f"ERROR: {m.name} cannot sustain {hz:g} Hz; measured ceiling is "
                      f"{feas.max_hz:.0f} Hz.\n"
                      f"       Re-run with --hz {feas.max_hz:.0f} or fewer vars, or pass "
                      f"--clamp to log at the ceiling.", file=sys.stderr)
                return 1

        out = unique_csv_path(args.outdir, m, hz)
        meta = write_meta(out, m, plan, args.elf, requested_hz=m.hz, feas=feas,
                          extra={"logged_hz": hz,
                                 "transport": lr.transport.cost_model.transport_name})
        print(f"# -> {out}\n# -> {meta}", file=sys.stderr)

        n = 0
        t_last = None
        fh = open(out, "w", newline="")
        writer = None
        try:
            for row in lr.stream(m.vars, hz=hz, duration=args.secs):
                if writer is None:
                    writer = csv.DictWriter(fh, fieldnames=list(row))
                    writer.writeheader()
                writer.writerow(row)
                n += 1
                t_last = row["t"]
                if args.quiet:
                    if n % 50 == 0:
                        print(f"\r# {n} samples", end="", file=sys.stderr)
                else:
                    print("  ".join(f"{k}={_fmt(v)}" for k, v in row.items()))
        except KeyboardInterrupt:
            print("\n# stopped", file=sys.stderr)
        finally:
            fh.close()
            rate = (n / t_last) if t_last else 0.0
            print(f"\n# wrote {n} samples to {out} (effective {rate:.1f} Hz)", file=sys.stderr)
    return 0


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

    sp = sub.add_parser("transports", help="list live-read transports and cost models")
    sp.set_defaults(func=cmd_transports)

    sp = sub.add_parser("read", help="one-shot read (needs hardware)")
    sp.add_argument("names", nargs="+", help="paths and/or group:<name> tokens")
    _transport_args(sp)
    sp.set_defaults(func=cmd_read)

    sp = sub.add_parser("watch", help="stream at N Hz (needs hardware)")
    sp.add_argument("names", nargs="+", help="paths and/or group:<name> tokens")
    sp.add_argument("--hz", type=float, default=20.0)
    sp.add_argument("--secs", type=float, default=None, help="stop after S seconds")
    sp.add_argument("--csv", help="also log samples to CSV")
    _transport_args(sp)
    sp.set_defaults(func=cmd_watch)

    sp = sub.add_parser("patch", help="write a float value to a RAM symbol (needs hardware)")
    sp.add_argument("symbol", help="DWARF symbol or path (e.g. mrac_state.pitch.What[0])")
    sp.add_argument("value", help="float value to write")
    sp.add_argument("--i-understand", action="store_true",
                    help="REQUIRED: acknowledge this writes to live RAM")
    sp.add_argument("--no-disarm-check", action="store_true",
                    help="skip arm-state check (logged at WARNING; bench use only)")
    sp.add_argument("--halt", action="store_true",
                    help="halt CPU before write, resume after (slower but safer)")
    sp.add_argument("--dry-run", action="store_true",
                    help="resolve address + show old value; do not write")
    sp.add_argument("--verify-only", action="store_true",
                    help="read old value and verify path; do not write")
    _transport_args(sp)
    sp.set_defaults(func=cmd_patch)

    sp = sub.add_parser("verify", help="check the ELF matches the flashed firmware (needs hardware)")
    sp.add_argument("--chunks", type=int, default=5, help="chunks sampled per flash segment")
    sp.set_defaults(func=cmd_verify)

    sp = sub.add_parser("writable", help="list RAM-writable members (DWARF-only, no hardware)")
    sp.add_argument("base_name", nargs="?", default="",
                   help="base symbol name (empty = all globals)")
    sp.add_argument("--format", choices=("text", "json"), default="text",
                   help="output format (default text)")
    sp.set_defaults(func=cmd_writable)

    sp = sub.add_parser("freshness",
                       help="read a field N times, verify it advances (catches wireless-bridge staleness)")
    sp.add_argument("field", help="symbol or path that increments over time (e.g. s_ekf.x[3])")
    sp.add_argument("--delay-ms", type=float, default=10.0,
                    help="delay between samples (default 10 ms)")
    sp.add_argument("--samples", type=int, default=3,
                    help="number of samples (default 3, minimum 2)")
    sp.add_argument("--require-monotonic", action="store_true",
                    help="for numeric fields, fail if values are not non-decreasing")
    _transport_args(sp)
    sp.set_defaults(func=cmd_freshness)

    sp = sub.add_parser("manifests", help="list logging manifests")
    sp.set_defaults(func=cmd_manifests)

    sp = sub.add_parser("budget", help="feasible sample rate for a manifest (no hardware)")
    _manifest_args(sp)
    _transport_args(sp)
    sp.set_defaults(func=cmd_budget)

    sp = sub.add_parser("log", help="log a manifest to a uniquely named CSV (needs hardware)")
    _manifest_args(sp)
    _transport_args(sp)
    sp.add_argument("--secs", type=float, default=None, help="stop after S seconds")
    sp.add_argument("--outdir", default="logs/livewatch", help="CSV output directory")
    sp.add_argument("--clamp", action="store_true",
                    help="log at the measured ceiling instead of refusing when --hz is too fast")
    sp.add_argument("--quiet", action="store_true", help="progress counter instead of every row")
    sp.set_defaults(func=cmd_log)
    return p


def _transport_args(sp):
    sp.add_argument("--transport", choices=("swd", "uart5"), default="swd")
    sp.add_argument("--uart5-port", help="manual UART5 COM port (overrides config.yaml)")
    sp.add_argument("--uart5-baud", type=int,
                    help="UART5 baud (overrides config.yaml; default 115200)")
    return sp


def _manifest_args(sp):
    """A manifest is named, or built ad-hoc from --vars; --hz overrides either."""
    sp.add_argument("manifest", nargs="?", help="manifest name from manifests.yaml")
    sp.add_argument("--vars", nargs="+",
                    help="ad-hoc variable list (paths and/or group:<name>) instead of a manifest")
    sp.add_argument("--name", help="name for an ad-hoc manifest (used in the CSV filename)")
    sp.add_argument("--hz", type=float, default=None, help="override the manifest sample rate")
    return sp


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args) or 0
    except LiveTransportError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    main()
