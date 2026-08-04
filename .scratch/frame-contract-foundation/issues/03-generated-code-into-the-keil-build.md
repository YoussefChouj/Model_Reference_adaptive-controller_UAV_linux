# How does generated frame-table code enter the Keil build?

Type: grilling
Status: closed — out of scope (destination redrawn 2026-07-31)

> **Out of scope.** No code is generated, so nothing needs to reach ARMCC. The precedent this
> ticket leaned on — `ground_station/livewatch/log_frames.md` as a source of truth that needs
> **no rebuild** to change — turns out to be the shape the redrawn map adopts wholesale: a
> manifest of symbol names, resolved on the host, never compiled. The two hard constraints
> restated here (`SUBSCRIBE_ADDR_SRAM_LO/HI` undefined in `JX_FLY.uvprojx`; never invoke UV4
> without `<pMon>` neutralisation) still hold and were carried onto the new map's Notes.

## Question

The table generates a firmware header and a host module, both committed. The firmware
half has to reach ARMCC, and Keil's project file lists every source explicitly.

What to settle:

- **Committed-only with a no-diff test, or a uvprojx pre-build step?** A pre-build step
  means the generator runs on every build on the operator's machine and inside
  `rebuild_and_flash`. A committed-only artefact means the generator is a developer
  command and the guard is a test that regenerates and asserts an empty diff.
- If a header is added to the project, **which file group** in `JX_FLY.uvprojx`, and does
  adding it disturb anything the flash path depends on.
- Whether the generator needs to be runnable from `tasks.py` and, if so, under which lane.

Two hard constraints bear on this directly:

- **`JX_FLY.uvprojx` must never define `SUBSCRIBE_ADDR_SRAM_LO/HI`.** The `#ifndef` guards
  in `API/subscribe.h` exist only so the gcc harness can retarget the allowlist at host
  memory. Defining them in the project would silently widen what a host can ask the drone
  to read. Guarded by `test_firmware_build_does_not_widen_the_address_allowlist`. Any
  uvprojx edit this ticket proposes must keep that test green.
- **Never invoke UV4 without neutralising `<pMon>`.** `<pMon>BIN\CMSIS_AGDI.dll` claims the
  CMSIS-DAP probe on project load; a bare invocation against a powered target halts the
  core. `rebuild_and_flash` wraps `safe_flash._pMon_neutralised()` and restores the
  project file byte-exact. A pre-build step that assumes a plain UV4 launch would
  reintroduce that hazard.

Precedent in the repo worth leaning on: `ground_station/livewatch/log_frames.md` is a
Markdown table that is the source of truth for stream frames and needs **no rebuild** to
change. `ground_station/livewatch/manifests.yaml` and `params_manifest.json` are the other
two data-as-contract artefacts.

Recommendation to argue against: committed-only, with regeneration as a test. A pre-build
step buys freshness the no-diff test already guarantees, and it puts a generator on the
critical path of the one build that must never surprise you.
