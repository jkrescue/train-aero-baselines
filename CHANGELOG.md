# Changelog

## [0.1.0] - 2026-11-19

### Added
- Leave-geometry-out evaluation of GeoTransolver, SMART and AB-UPT on the train CFD data
  (8 folds, nose-shape and formation-length families).
- PhysicsNeMo-CFD benchmark plugin: `train_aero` adapter, `recipe_surface` model wrapper,
  `side_force` / `roll_moment` / `roll_moment_lee` metrics.
- Final results of 47 runs: 8 folds × 3 models, seed noise (n2, l2), learning-rate sweep,
  supervision points and area-weighted loss (n2), centred AB-UPT diagnostic; report in Chinese.
- Checkpoints of all 47 runs as release assets, indexed in `results/checkpoints.json`.
