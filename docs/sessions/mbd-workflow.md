# MBD workflow session (2026-07-28)

> Moved verbatim out of CLAUDE.md on 2026-08-09 to cut per-turn
> context churn. CLAUDE.md keeps a compact index pointing here.

### MBD Workflow Session (2026-07-28) — PAUSED, still unreviewed

**Plan**: read `.agent_contracts/mbd_workflow/README.md` first — it holds the shared context, safety constraints and verified environment facts. Then `01-sil-gate.md`, `02-probe-free-build.md`, `03-build-budget-gate.md`, `04a-sixdof-trajectory.md`, `04b-gazebo-bringup.md`. Durable decisions are in memory `project_mbd_workflow_plan`.

**Governing principle**: `sim/` is normative for the **algorithm**; firmware is normative for **integration**. A C↔Python mismatch is a suspected firmware bug, investigated every time.

**Agent status at checkpoint** (all five ran in ONE shared worktree, branch `chore/agent-workflow-hardening` — no isolation):

| Spec | Evidence on disk | State |
|---|---|---|
| 1 SIL gate | `sil_gate/` | ran |
| 2 build/flash | `ground_station/flashtool/build_id.py`, `USER/build.log`, `USER/flash.log` | ran |
| 3 budget gate | `ground_station/build_budget/` | ran |
| 4a 6-DOF | `sim/plant.py` 137→663 lines, `sim/outer_loops.py`, `sim/trajectories.py` (new) | ran |
| 4b Gazebo | none | **correctly refused** — 4a's deliverables were absent at 21:56; its report is right, though it wrongly claimed `docs/` doesn't exist (only `docs/requirements.md` is missing) |

**REVIEW DONE (2026-07-29).** All 373 main-tree tests pass; alleged 4a "flaky" tests are seeded and stable (3× green — the earlier failures were mid-edit runs, not seed sensitivity). Verdicts:

| Spec | Verdict | Blocking findings |
|---|---|---|
| 1 sil_gate | **ACCEPT** | none; C99 fallback + subprocess design sound, b6bd27b pinned & reachable |
| 2 flashtool | **REWORK before use — scope: `safe_flash`'s `gate`/`build`/`all` subcommands and `build_id.py` ONLY. This does NOT apply to `python -m ground_station.flashtool.rebuild_and_flash`, which is the working pipeline (4 clean runs) and never calls the defective gate — it imports only `_pMon_neutralised` and `_run_uv4`, verified 2026-08-09.** | (a) `identity_from_elf` compares target `(magic,ctr,epoch,fp)` against `(magic,ctr,0,0)` → `check_identity` can NEVER pass on stamped firmware; (b) identity = `OBJ/.build_counter` file, not the ELF → build-without-flash + custody restore gives false refusal, counter tracks the dir not the ELF; (c) plain `gate` cmd now always fails until a stamped build is flashed (regression — current firmware has no `build_id` symbol); (d) `all` gate-fail path exits without `artifact_custody.restore` → stale-axf hazard it was built to close; (e) unreferenced `build_id[4]` may be stripped by armlink unused-section elimination — needs `--keep` or a reference. Fails **safe** (refuses), never unsafe. pMon neutralisation restores byte-exact; main-tree uvoptx verified intact (`CMSIS_AGDI.dll` still set). |
| 3 build_budget | **ACCEPT w/ operator step** | baseline seeded from partial `.htm` tail (5 warning identities, Code=80908) — first honest run will fail; reseed from next verified clean build |
| 4a 6-DOF | **REWORK torque path** | skeleton right (`ω×Iω` present, quaternion, Euler@dt=0.005, tensor once, metrics pure). But: **MRAC/rate loop absent from trajectory lane** — `run_trajectory` wires `OuterLoop→RigidBodyPlant` directly; plant "emulates" the inner loop via hand-tuned fudge constants (`dF_roll_unit=0.005` "slightly larger for clear response", `tau=diff*r*0.25` where comments derive 0.5, `_YAW_TORQUE_PER_UNIT` dimensionally incoherent, dead code: `motor_cmd`, `K_diff`, motor positions, `cg_below_arm_plane` never used). Spec said outer loops sit above `ControlLoop.tick`; trajectories not registered in `scenarios.py`. Thesis metrics from this lane measure a P/PD cascade around a fake rate response, NOT the MRAC drone. |
| 4b Gazebo | **ACCEPT w/ 1 defect + integration debt** | URDF passes the stated CG trap (inertial origin 0, offset visual-only). NEW defect: motor links add 4×0.030 kg + own inertia at r=0.2 m on top of full measured mass/tensor in body link → Gazebo composite ≈1.416 kg, Izz ≈0.0245 (+65%). Motor masses must be 0 (or body de-massed). Work is UNCOMMITTED in worktree `C:\Users\Acer\Desktop\UAV_lab\wbw-4b-gazebo` (branch `spec/4b-gazebo-bringup`, 0 commits); its `plant.py`/`test_seams.py` = main-tree 4a + additive GazeboPlant probe (clean delta); `metrics.py` identical. |

**COMMITTED (2026-07-29)** on `chore/agent-workflow-hardening`: 4a `bfb68c6` (caveats in message) → sil_gate `565ba5a` → flashtool `9279847` (marked NOT YET USABLE, findings a–e in message) → build_budget `0f947b5` → lane wiring `4d9b795` → 4b `0f65d60` (**motor-mass double-count FIXED**: motor inertials now epsilon 1e-6 kg, new `test_urdf_composite_mass_and_izz_match_measured` pins the lumped composite; jx_fly.urdf regenerated) → `1875706` fix: pytest.ini lacked `build_budget/tests` and tasks.py LANES lacked flashtool+budget (46+59 tests were invisible). **Full suite now 443 green in both runners.** 4b worktree + branch `spec/4b-gazebo-bringup` removed after integration. Working tree now holds ONLY the streaming-session files (subscribe/usart/stream, uvoptx, API/tests/, build/flash logs, scratch.py) — uncommitted, pending the multi-slot flash test. Remaining rework debt: flashtool findings a–e (confined to `safe_flash`'s gate/`build_id`; `rebuild_and_flash` is unaffected and works); 4a torque path (MRAC into trajectory lane); budget baseline reseed after next clean build. `/implement-spec` skill updated 2026-07-29: journal location for flat specs, commit-to-task-branch, uncommitted-prereq handling, flaky-test rule, journal-in-main-tree.

**Done this session besides the specs**: headless Keil build proven working (`Start-Process -Wait -NoNewWindow`, no stdio capture; memory `project_headless_build_unreliable` corrected); `~/.cursor/skills/implement-spec/SKILL.md` gained repo-agnostic worktree isolation (§3a provision gitignored paths discovered via `git check-ignore`, link read-only / **copy** written) + exclusive-resource locking (§3b) + a dependency precondition check in §2.
