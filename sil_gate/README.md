# SIL Gate — host-compiled firmware C ↔ `sim/` equivalence

A pytest suite that compiles real firmware C with `gcc` on the developer's laptop
and compares its numerical behaviour against the corresponding Python module in
`sim/`. The firmware source is **never modified and never flashed**.

| Spec | Source of truth |
|------|-----------------|
| `01-sil-gate.md`   | the contract this directory fulfils |
| `README.md`        | this file — usage and layout |
| `shim/`            | host-only include stubs, clearly marked test-only |
| `compiler.py`      | gcc discovery + flag bundle (FPU parity + strictness) |
| `linker.py`        | cffi ABI loading + symbol resolution |
| `runner.py`        | trajectory driver + numerical comparison + growth check |
| `tests/`           | pytest cases (current EKF, self-test, historical bad) |
| `DEVIATIONS.md`    | documented firmware-vs-model differences (read this when a mismatch is intentional) |

## Run

The gate runs as part of the standard suite. From the repo root:

```bash
.venv/Scripts/python.exe tasks.py test           # full suite (includes sil_gate)
.venv/Scripts/python.exe tasks.py test sil       # only the sil lane (sil_gate/tests)
.venv/Scripts/python.exe -m pytest -q sil_gate/tests    # one-shot invocation
```

A first run takes ~10 s (gcc compile + dlopen). Subsequent runs are near-instant
because the compile is cached by content hash under `sil_gate/build/`.

If `gcc` cannot be found, the suite skips with a clear message — not a failure —
because `gcc` is optional on a developer laptop. Tests that need it are marked
`@pytest.mark.skipif(no_gcc, ...)`.

## What it tests

For now, only `API/ekf.c` against `sim/ekf.py` — the spec's explicit "ekf.c first"
order. `mrac.c` follows in a later task once the pattern is proven.

For each entry-point function, the gate drives the C and Python implementations
with identical inputs over a 2000-tick trajectory at the firmware's 200 Hz
`MRAC_DT` and compares every tick of the trajectory. The pass criterion has
**both** parts:

1. the per-tick relative difference stays within a documented tolerance
   (current default: `1e-5` relative — coarser than the spec's suggested `1e-6`
   because the host gcc 6.3.0 with `-msse2` exposes some last-bit noise on
   `pentium4`; tighten only if the observed noise floor permits); AND
2. the trajectory does **not** exhibit sustained growth (sliding-window slope
   of `|delta|` must stay under `1e-3` per second). A growing delta is a
   structural defect regardless of current magnitude — the EKF's documented
   unobservable gyro-bias states make this particularly load-bearing.

A deliberately perturbed copy of `ekf.c` (the **self-test**) must make the gate
fail loudly. A pass that has never failed is not evidence that the gate works.

## Files modified

None outside this directory. The gate is a *consumer* of `API/`, `Global_file/`,
`sim/`. If those change, rebuild via `rm -rf sil_gate/build/` and re-run.

See `DEVIATIONS.md` for documented firmware-vs-model differences that the gate
silences.