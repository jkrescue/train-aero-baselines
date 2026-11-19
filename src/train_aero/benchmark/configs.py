"""Write the inputs of a PhysicsNeMo-CFD benchmark run.

    python -m train_aero.benchmark.configs [--conf-dir DIR] [--results-dir DIR]

1. Per finished run: `<run>/bench_infer_config.yaml`, the recipe's `conf/infer.yaml` composed
   with exactly the overrides `scripts/run_one.sh` passes to `src/infer.py`.  Together with the
   `.mdlus` checkpoint this is the run's model package.
2. Per fold: `<conf-dir>/train_aero_<fold>.yaml`, a benchmark config in the layout of
   `workflows/benchmarking/conf/config_matrix_surface_custom.yaml` that lists every finished
   run of the fold as a `recipe_surface` model.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from train_aero.folds import (
    A_REF_M2,
    FULL_MESH_SAMPLING,
    MODELS,
    default_dataset_suffix,
    family_of,
    fold_summary,
    geometry_of,
    recipe_model_config,
)
from train_aero.paths import Layout, layout


def run_label(meta: dict) -> str:
    tag = "" if meta["tag"] == "-" else f"__{meta['tag']}"
    return f"{MODELS[meta['model']]}/seed{meta['seed']}{tag}"


def infer_overrides(meta: dict, run: Path) -> list[str]:
    """Hydra overrides of the run's inference, mirroring scripts/run_one.sh."""
    family, fold, model = meta["family"], meta["fold"], meta["model"]
    suffix, measure_weighted, extra = default_dataset_suffix(model), "false", []
    for tok in meta.get("overrides", "").split():
        if tok.startswith("MW="):
            measure_weighted = tok[3:]
        elif tok.startswith("DS="):
            suffix = "_" + tok[3:]
        elif not tok.startswith(("RES=", "training.")):      # training-only overrides
            extra.append(tok)
    return [f"model={recipe_model_config(model, family)}", f"dataset=ev_{fold}_orig{suffix}",
            "compile=false", "precision=float32", "run_id=train", f"measure_weighted={measure_weighted}",
            f"sampling_resolution={FULL_MESH_SAMPLING}", "infer_split=test", f"checkpoint_dir={run}",
            f"output_dir={run}/infer", f"force_coefficients.reference_area={A_REF_M2}",
            f"training.seed={meta['seed']}", *extra]


def compose_infer_config(lay: Layout, meta: dict, run: Path, out: Path) -> None:
    sys.path.insert(0, str(lay.recipe / "src"))
    from hydra import compose, initialize_config_dir
    from omegaconf import OmegaConf
    from physicsnemo import datapipes  # noqa: F401  (registers the ${dp:...} resolver)

    with initialize_config_dir(config_dir=str(lay.recipe / "conf"), version_base=None):
        cfg = compose("infer", overrides=infer_overrides(meta, run))
    OmegaConf.save(cfg, out)


def benchmark_config(fold: str, models: list[dict], cases: list[str], results_dir: Path, truth_dir: Path) -> dict:
    coeff = 1.0 / A_REF_M2
    pair = lambda name, key: {"name": name, "true_key": f"{key}_true", "pred_key": f"{key}_pred"}  # noqa: E731
    return {
        "defaults": ["_self_"],
        "hydra": {"run": {"dir": "${run.output_dir}"}, "output_subdir": "hydra", "job": {"chdir": False}},
        "case_id": None,
        "run": {"device": "cuda:0", "output_dir": str(results_dir / fold), "seed": 42, "batch_size": 1,
                "save_inference_mesh": False, "distributed": False, "fail_on_any_metric_nan": True,
                "metrics_cache": {"enabled": False}},
        "benchmark": {"mode": "matrix", "models": models,
                      "datasets": [{"name": "train_aero", "label": fold, "root": str(truth_dir),
                                    "kwargs": {"fold": fold}}],
                      "reproducibility": {"log_env": False, "save_artifacts": True}},
        "output": {"surface_interpolate_point_to_cell_for_metrics": False,
                   "mesh_field_names": {"pressure": "pressure_pred", "shear_stress": "wall_shear_stress_pred"},
                   "ground_truth_mesh_field_names": {"pressure": "pressure_true",
                                                     "shear_stress": "wall_shear_stress_true"}},
        "metrics": ["l2_pressure", "l2_shear_stress", "l2_pressure_area_weighted",
                    {"name": "drag", "coeff": coeff}, {"name": "lift", "coeff": coeff},
                    {"name": "side_force", "coeff": coeff}, "roll_moment", "roll_moment_lee"],
        "reports": {
            "enabled": True, "save_comparison_meshes": False, "comparison_mesh_subdir": "comparison_meshes",
            "visual_case_ids": [c for c in cases if c.endswith("yaw12")][:1],
            "visuals": [
                {"name": "field_comparison_surface", "canonical_keys": ["pressure"], "view": "xz"},
                {"name": "line_plot_centerlines", "canonical_key": "pressure", "plot_coord": "x",
                 "normalize_factor": 1.0, "z_clip": 10.0, "y_slice_origin": [0, 0, 0],
                 "xlabel": "x [m]", "ylabel": "Cp",
                 "true_line_kwargs": {"label": "CFD"}, "pred_line_kwargs": {"label": "Prediction"}},
                {"name": "design_scatter", "pairs": [pair("Cd", "drag"), pair("Cs", "side_force"),
                                                     pair("CMx_lee", "roll_moment_lee")]},
                {"name": "design_trend", "pairs": [pair("Cs", "side_force"), pair("CMx_lee", "roll_moment_lee")]},
            ]},
    }


def finished_runs(lay: Layout) -> list[tuple[Path, dict]]:
    out = []
    for rj in sorted(lay.runs.rglob("run.json")):
        meta = json.loads(rj.read_text())
        if meta["train_rc"] == 0 and list((rj.parent / "train/checkpoints").glob("*.mdlus")):
            out.append((rj.parent, meta))
    return out


def main() -> None:
    lay = layout()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--conf-dir", type=Path, default=lay.bench / "conf")
    ap.add_argument("--results-dir", type=Path, default=lay.bench / "results")
    args = ap.parse_args()

    per_fold: dict[str, list[dict]] = {}
    for run, meta in finished_runs(lay):
        out = run / "bench_infer_config.yaml"
        if not out.exists():
            compose_infer_config(lay, meta, run, out)
        per_fold.setdefault(meta["fold"], []).append({
            "name": "recipe_surface", "label": run_label(meta), "inference_domain": "surface",
            "checkpoint": str(run / "train/checkpoints"),
            "stats_path": str(lay.fold_dir(meta["fold"], "shuf") / "norm_stats.json"),
            "kwargs": {"recipe_config": str(out), "family": meta["family"]}})

    args.conf_dir.mkdir(parents=True, exist_ok=True)
    for fold, models in per_fold.items():
        geometries = fold_summary()[fold]["test_geometries"]
        cases = sorted(d.name for d in lay.base_dataset(family_of(fold)).iterdir()
                       if geometry_of(d.name) in geometries)
        cfg = benchmark_config(fold, models, cases, args.results_dir, lay.bench / "truth")
        (args.conf_dir / f"train_aero_{fold}.yaml").write_text(
            f"# Generated by train_aero.benchmark.configs: PhysicsNeMo-CFD benchmark config, fold {fold}\n"
            "# (same layout as workflows/benchmarking/conf/config_matrix_surface_custom.yaml)\n"
            + yaml.safe_dump(cfg, sort_keys=False))
        print(fold, len(models), "models")


if __name__ == "__main__":
    main()
