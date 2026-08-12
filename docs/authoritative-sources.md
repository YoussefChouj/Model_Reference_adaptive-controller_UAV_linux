# Authoritative Sources — Workspace Index

Curated authoritative sources for this repo's adaptive-control research and
simulation pipeline. **Cite these, not blog posts.** When in doubt, fetch the
canonical source again and quote it.

Created: 2026-08-13. Last reviewed: 2026-08-13.

## How to use this doc

Each section names a topic, the canonical source(s), and the path to cached
markdown when one exists. Cache path `.firecrawl/<slug>.md` means the file was
pulled with `firecrawl scrape <url> -o .firecrawl/<slug>.md`. Cache files are
gitignored; re-pull if a source has moved.

## Primary indexes (start here)

| Topic | Source | Cache |
|---|---|---|
| PX4 flight logs (docs) | https://docs.px4.io/main/en/log/flight_log_analysis | `.firecrawl/px4-log-analysis-main.md` |
| PX4 bulk log download | https://docs.px4.io/main/en/dev_log/flight_log_analysis_statistical | `.firecrawl/px4-flight-logs-bulk.md` |
| PX4 flight_review (web app) | https://github.com/PX4/flight_review | `.firecrawl/px4-flight-review-readme.md` |
| PX4 public log thread | https://discuss.px4.io/t/public-log-files-of-a-standard-flight-for-analysis-teaching-purposes/19484 | `.firecrawl/px4-discuss-public-logs.md` |
| Neural-Fly paper (Caltech) | https://arxiv.org/abs/2205.06908 (Science Robotics 2022) | `.firecrawl/neural-fly-arxiv.md` |
| Neural-Fly code+data | https://github.com/aerorobotics/neural-fly | (scrape failed HTTP/2; retry with `interact` or `parse` on the PDF) |
| UAV-SEAD dataset | https://arxiv.org/abs/2602.13900 — 1396 logs, 52h | — |
| UAV-SEAD Hugging Face mirror | https://huggingface.co/datasets/aykutkabaoglu/uav-flight-anomaly-dataset | `.firecrawl/uav-sead-hf.md` |
| IDF-DS benchmark (fixed-wing) | https://pmc.ncbi.nlm.nih.gov/articles/PMC12982758/ — 240 flights, 32h, Zenodo 10.5281/zenodo.16992975 | — |
| Chowdhary 2010 CL briefing | `raw/papers/2026-08-12-Chowdhary-2010-ConcurrentLearning-briefing.md` | — |

## PX4 `.ulog` datasets — concrete leads

For `prior-13b` (SINDy on PX4 data) and any other spec needing real flight
logs. **Quadrotor logs are scarce; most public datasets are fixed-wing or
focused on anomaly detection.**

### Lead 1 — `logs.px4.io` reference flights (gated CDN)

The PX4 forum thread above names two concrete quadrotor `.ulg` IDs hosted on
`logs.px4.io`:

- `8083fef0-b267-4c91-976e-3805bdb885e9` — Holybro QAV-250, Feb 2020
- `89b87d6f-d286-4703-b36b-573191a907f1` — Holybro QAV-250, same session

Both have acc, gyro, mag, baro, GPS; medium quad, low vibration, "a lot of
motion". This is the cleanest public quadrotor log we have a direct pointer to.

**CDN URL** (confirmed via `firecrawl interact` 2026-08-13):
`https://cdn.logs.px4.io/<uuid>.ulg`. **Gated**: CloudFront/S3 returns 403 to
anonymous requests. The download API is `https://review.px4.io/download?log=<id>`
which 302s to the CDN. Need a browser session cookie from `plot_app` to
download. The official `flight_review/download_logs.py` script handles this
internally with a 6s rate limit.

Direct download is not feasible from a curl-only session. Use either:
- `firecrawl interact` (slow, ~40s per file, brittle)
- `flight_review/download_logs.py` (the official path)
- A different dataset (Lead 3 below)

Browse more: `https://logs.px4.io/browse`.

### Lead 2 — `flight_review/download_logs.py` (bulk)

PX4's `flight_review` repo ships a `download_logs.py` script for bulk
download from the same server. Use this when you need many flights, not
just a reference one.

Repo: https://github.com/PX4/flight_review (see `Tools/`).
Docs: https://docs.px4.io/main/en/dev_log/flight_log_analysis_statistical.

### Lead 3 — UAV-SEAD (large, anomaly-focused)

1396 real PX4 `.ulg` flights, 52h, indoor + outdoor. Designed for state-
estimation anomaly detection (not adaptive control), so most flights are
nominal. **Useful for plant-dynamics SINDy on real data**, less useful for
controller benchmarks.

- Paper: https://arxiv.org/abs/2602.13900
- HF mirror (extracted estimator states, not raw `.ulg`): https://huggingface.co/datasets/aykutkabaoglu/uav-flight-anomaly-dataset
- DOI: 10.57967/hf/7772
- License: cc-by-4.0

**Caveat**: HF dataset is pre-extracted (144 rows parquet, 21 topic groups).
Raw `.ulg` is at the paper's repository (Kabaoglu's GitHub — confirm via
paper PDF).

### Lead 4 — IDF-DS (fixed-wing, peer-reviewed)

240 fixed-wing UAV flights, 32h. PX4 `.ulg` format. Peer-reviewed in PMC.
**Not quadrotor** — wrong airframe class for `prior-13b` but useful as a
contrast or for cross-class SINDy demonstrations.

- Paper: https://pmc.ncbi.nlm.nih.gov/articles/PMC12982758/
- Data: https://zenodo.org/records/16992975
- DOI: 10.5281/zenodo.16992975

## SINDy-on-UAV literature

These are the relevant SINDy papers an agent should cite when discussing
`prior-13b` or plant-discovery:

| Paper | URL | Relevance |
|---|---|---|
| PD-Based and SINDy Nonlinear Dynamics Identification of UAVs | https://arxiv.org/html/2410.11791v1 | Closest direct match: SINDy for UAV plant ID |
| Sparse Identification of Nonlinear Dynamics-Based MPC | https://ietresearch.onlinelibrary.wiley.com/doi/full/10.1049/cth2.70049 | Multirotor SINDy for MPC; mass uncertainty handling |
| Data-driven Discovery of Quadrotor Equations of Motion via SINDy | https://pure.kfupm.edu.sa/en/publications/data-driven-discovery-of-the-quadrotor-equations-of-motion-via-sp/ | Plain SINDy on quad EoM |
| SINDy and PD-Based UAV Dynamics Identification for MPC (MDPI Drones) | https://www.mdpi.com/2504-446X/9/1/71 | Companion to the arXiv 2410.11791 paper |

## MRAC / adaptive-control literature

| Paper | URL | Relevance |
|---|---|---|
| Neural-Fly (O'Connell et al. 2022) | https://arxiv.org/abs/2205.06908 | DAIML + composite adaptation, 12 min data, exponential stability |
| Chowdhary & Johnson CDC 2010 / PhD thesis (arXiv:1012.0806) | `raw/papers/2026-08-12-Chowdhary-2010-ConcurrentLearning-briefing.md` | Concurrent learning, history stack, rank condition |
| MathWorks MRAC quadrotor example | https://www.mathworks.com/help/slcontrol/ug/quadrotor-control-using-model-reference-adaptive-control.html | Reference implementation |
| MRAC of Multirotor for Dynamic Missions (Maki, Zhao) | https://www.semanticscholar.org/paper/Model-Reference-Adaptive-Control-of-Multirotor-for-Maki-Zhao/1633f6c65833afb1f58464d87259193c4bf45443 | MIMO MRAC for multirotor |
| Adaptive Quadrotor with Partial Actuator Failure | https://dr.ntu.edu.sg/server/api/core/bitstreams/93d88f65-fde3-4e13-86ae-0c7600525fef/content | MRAC + dynamic inversion for actuator faults |
| RKHS-MRAC (Virginia Tech thesis) | https://vtechworks.lib.vt.edu/items/f78ec361-68f3-4d98-94d5-87f32cbe6a32 | RKHS basis vs classical MRAC |

## PX4 reference airframe specs

When validating `sim/CANONICAL_AIRFRAME` or comparing sim to firmware, the
canonical reference vehicle is the **Holybro X500 v2**:

- https://docs.px4.io/main/en/frames_multicopter/holybro_x500v2_pixhawk6c.html

The `CANONICAL_AIRFRAME` in `sim/` should be checked against this.

PID tuning guide (cross-check adaptive-law starting points):
https://docs.px4.io/main/en/config_mc/pid_tuning_guide_multicopter

## How to add a new source

When you find a new authoritative source that an agent should cite later:

1. Fetch with Firecrawl: `firecrawl scrape "<url>" -o .firecrawl/<slug>.md`.
2. Add a row to the right table in this file with: topic, URL, one-line
 relevance note, and cache path (or "—" if not cached).
3. If the source contradicts or refines something already cited, **flag it in
 `docs/decisions.md`** — silent replacement of an old citation is a bug.

## What does NOT go in this doc

- Blog posts, Medium articles, YouTube transcripts — useful for triage, not
 citation. Quote them only when they lead to a primary source.
- Stack Overflow / forum answers that paraphrase docs.
- Marketing pages.
- Anything that has been superseded by a newer paper from the same authors
 (cite the newer one unless the older one is the foundation of a method).