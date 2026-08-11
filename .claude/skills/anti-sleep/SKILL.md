---
name: anti-sleep
description: >
  Keep the Linux workstation awake reliably using systemd-inhibit for a set duration
  or while a process runs. Use for "don't let my computer sleep", "anti-sleep",
  "keep the screen on", or long autonomous agent runs. Survives agent shell cleanup.
---

# Anti-Sleep (Linux / systemd-inhibit)

Use the bundled launcher from this skill directory. It uses `systemd-inhibit` to prevent
sleep/suspend while a process runs.

## Required workflow

1. Inspect current state:

```bash
scripts/anti-sleep.sh status
```

2. If `status` reports an active session and the user requested a new duration, stop the old
   session. Never ask for confirmation — just stop it.

```bash
scripts/anti-sleep.sh stop
```

3. Start the new timer:

```bash
scripts/anti-sleep.sh start 10800    # 3 hours (seconds)
```

4. In a **separate shell call after the start command has returned**, verify:

```bash
scripts/anti-sleep.sh verify
```

Only report success when verification returns `STATUS=running`. Confirm the PID, flags,
and wall-clock expiry. If verification fails, run `stop` and do not claim the workstation
is protected.

## Status and stop

```bash
scripts/anti-sleep.sh status
scripts/anti-sleep.sh stop
```

## Fallback

If `systemd-inhibit` is not available, use `caffeinate` (Linux has `caffeinate` from the
`caffeine` package on some distros) or a visible persistent terminal/cmux pane.
