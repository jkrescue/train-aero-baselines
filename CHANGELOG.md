# Changelog

## [0.1.0] - 2026-11-19

### Added
- Leave-geometry-out evaluation of GeoTransolver, SMART and AB-UPT on the train CFD data
  (8 folds, nose-shape and formation-length families).
- PhysicsNeMo-CFD benchmark plugin: `train_aero` adapter, `recipe_surface` model wrapper,
  `side_force` / `roll_moment` / `roll_moment_lee` metrics.
- Interim results (7 of 8 folds, learning-rate sweep, centred AB-UPT diagnostic) and the report.
