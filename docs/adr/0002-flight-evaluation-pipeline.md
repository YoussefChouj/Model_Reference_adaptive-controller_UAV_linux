# Flight evaluation: champion store keyed by (mode × tuning-config), ranked by health-gated tracking error

**Status:** accepted

## Context

Every preset path run auto-produces a thin `summary.md` (params only). A rich metrics engine
(`deep_analysis.py`) already existed but (a) only ran on a manual button, (b) scored only the
attitude/rate loops — never `locx`/`locy` position, which *is* the path-tracking signal — and
(c) recorded a **hardcoded** firmware-param snapshot instead of the run's real params. The goal is
holistic per-run understanding plus a way to find and compare the best run per path type.

## Decision

1. **Champion store keyed by `(mode × tuning-config)`**, where the config key is a hash of the
   ranking-relevant params/gammas — not by mode alone. Stored under `ground_station/champions/<mode>/`
   with `best_overall.json`, `leaderboard.json` (top-N), and `by_config/cfg_<hash>.json`.
2. **Ranking scalar = position/geometric tracking RMSE**, not the composite at-a-glance score, and
   **health-gated**: a run with any `CRITICAL` MRAC alert is ineligible to be champion regardless of RMSE.
3. **Real run params are forwarded** from the GUI's `_auto_log_params` into `deep_analysis`; the static
   `snapshot_firmware_params()` is demoted to a fallback only.
4. `results/<stem>.json` schema stays **append-only** (the `analyze-results` skill consumes it).

## Considered options

- *Champion per mode only* — simpler, but a better-tuned run erases the prior champion, destroying the
  tuning-sweep comparison that the thesis needs. Rejected.
- *Rank by composite 0–100 score* — one number, but its per-mode weights are arbitrary; ranking on it
  would make "best" a function of weighting taste rather than measured accuracy. Composite is reported,
  not used to rank.

## Consequences

- The config hash is part of the on-disk contract: changing which params feed the hash, or changing the
  ranking metric, **orphans accumulated champion records** — hence this ADR. Migrations must rehash.
- Health-gating means an aggressive tuning with great RMSE but a `CRITICAL` alert will (correctly) never
  be crowned, which can look surprising ("lower RMSE run isn't the champion") without this context.
