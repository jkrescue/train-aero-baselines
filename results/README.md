# Results

Exported from the work directory by `python -m train_aero.release.export`; do not edit by hand.

| Path | Content |
|---|---|
| `summary.md` | all tables of the report: per fold, fold means, paired differences, seed noise, variants, cost |
| `benchmark/<fold>/benchmark_results.{json,csv}` | PhysicsNeMo-CFD benchmark output, per case and model |
| `figures/<fold>/` | benchmark report visuals (surface Cp, centre-line Cp, design trend / scatter) |
| `baselines/<fold>.json` | no-learning baselines |
| `runs/<family>/<model>/<fold>/<run>/` | `run.json` (commit, overrides, time, memory), `history.csv` (per-epoch curves), `resolved_config.yaml`, `bench_infer_config.yaml`, `score.json` (cross-check) |
| `checkpoints.json` | release assets: run, model class, size, SHA-256 |

Run names: `seed<k>` for default settings, `seed<k>__<tag>` for variants (`lr*`, `pts*`,
`areaw`, `centered`). Model ids: `gt` GeoTransolver, `smart` SMART, `abupt` AB-UPT.
