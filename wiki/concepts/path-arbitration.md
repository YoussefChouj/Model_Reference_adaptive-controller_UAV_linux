---
title: Path Arbitration
type: concept
tags: [autonomy, safety, path-planning]
created: 2026-04-13
updated: 2026-04-14
sources: [TASK/AutoflyTask.c, TASK/send_data.c, Global_file/global_declare.h]
related_files: [TASK/AutoflyTask.c, TASK/send_data.c, Global_file/global_declare.h]
relations:
  - type: safety_critical_for
    target: "[[AutoflyTask]]"
---

Path arbitration enforces a hard invariant: at most one autonomous path family is active per cycle. The enforcing function is:

`static void AutoflyTask_PathArbitrate(void)` (`TASK/AutoflyTask.c:15`)

## Full Arbitration Logic

Exact branch behavior:
- If `sinusoid_path.active` is true, it disables `circle_path.active` and clears `TWC.execute` (`TASK/AutoflyTask.c:17-20`)
- Else if `circle_path.active`, it disables sinusoid and clears `TWC.execute` (`TASK/AutoflyTask.c:20-23`)
- Else if `TWC.execute != 0`, both procedural paths are disabled (`TASK/AutoflyTask.c:23-26`)

After arbitration, task dispatch is:
- circle branch first (`TASK/AutoflyTask.c:105-107`)
- else sinusoid (`TASK/AutoflyTask.c:107-108`)
- TWC is consumed downstream by [[StabilizerTask]] `Update_Des` logic (`TASK/StabilizerTask.c:396,422,465`)

## Constraints

Activation/deactivation command interface in `Process_GroundStation_Command()`:
- TWC (`CMD 0x0A`) sets targets and `TWC.execute` (`TASK/send_data.c:580-595`)
- Sinusoid (`CMD 0x0B`) sets params and `sinusoid_path.active` (`TASK/send_data.c:597-626`)
- Circle (`CMD 0x0C`) sets params and `circle_path.active` (`TASK/send_data.c:628-653`)
- Global abort (`CMD 0x0D`) calls `GroundStation_AbortAllPaths()` (`TASK/send_data.c:655-660`)

Also, each path can self-deactivate on duration expiration:
- Sinusoid clears `active` and `TWC.execute` (`TASK/AutoflyTask.c:94-98`)
- Circle clears `active` and `TWC.execute` (`TASK/AutoflyTask.c:50-54`)

## Simultaneous Activation Case

If two path flags become active at once (for example due to back-to-back host commands), arbitration deterministically resolves the conflict on the next 5 ms cycle. Priority order is:

`sinusoid > circle > TWC`

because the function checks sinusoid first, then circle, then TWC (`TASK/AutoflyTask.c:17-26`). This order is the invariant preventing multi-writer setpoint conflict.

## Command Trigger Mapping

Path activation is host-command driven:
- `0x0A idx=4` toggles TWC execute
- `0x0B idx=7` toggles sinusoid active
- `0x0C idx=6` toggles circle active

No timeout watchdog outside per-path `duration` logic is present; deactivation is by explicit command, duration completion, or global abort/dangerous-stop mode.

## See Also

- [[Virtual RC Authority]]
- [[AutoflyTask]]
- [[Autonomous Path Generation]]
- [[Ground-Station Binary Protocol]]

<!-- recent_change:2026-07-25 -->
## Recent change (2026-07-25)

Auto-flagged by path_refresh. Files affected in this session:
- `TASK/StabilizerTask.c`

Run `/wiki ingest` or `python -m graphify --update` to verify rationale still holds. Remove this section if confirmed unchanged.
