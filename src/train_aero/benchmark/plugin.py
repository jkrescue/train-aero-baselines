"""PhysicsNeMo-CFD benchmark plugin: dataset adapter, model wrapper and extra metrics.

Imported by `train_aero.benchmark.launch` before the official entry point
`physicsnemo-cfd/workflows/benchmarking/main.py` runs.  Only the documented extension
points are used; no PhysicsNeMo-CFD file is edited.

register_adapter("train_aero", TrainAeroAdapter)
    The test cases of one leave-geometry-out fold as `CanonicalCase` (surface cells of the
    curated mesh, Cp / Cf, coordinates in metres).
register_model("recipe_surface", RecipeSurfaceWrapper)
    Runs inference inside the benchmark: loads the trained `.mdlus` checkpoint and executes
    the same steps as the recipe's `src/infer.py` (build_dataloaders -> collate ->
    model(**forward_kwargs) -> normalize_output_to_tensordict -> redimensionalize), importing
    those functions from the recipe instead of copying them.
register_metric("side_force" | "roll_moment" | "roll_moment_lee")
    side_force reuses the built-in `lift` metric with direction +y; roll moments use
    `train_aero.physics.integrate_moments` (EN 14067-6 lee-rail moment).

Force convention (verified): the case VTP keeps the curated cell ordering, for which
pyvista's cell normals point INTO the body.  With that ordering the built-in
`compute_drag_and_lift` (coeff = 1 / A_ref) equals `train_aero.physics.integrate_forces`.
Reversing the cell ordering flips the pressure term.
"""
from __future__ import annotations

import functools
import re
import sys
from pathlib import Path
from typing import Any, ClassVar

import numpy as np
import pyvista as pv
import torch
from physicsnemo.cfd.evaluation.datasets.adapter_registry import DatasetAdapter, register_adapter
from physicsnemo.cfd.evaluation.datasets.schema import CanonicalCase, build_predictions_dict
from physicsnemo.cfd.evaluation.metrics.builtin.forces import lift_error
from physicsnemo.cfd.evaluation.models.model_registry import CFDModel, register_model
from physicsnemo.cfd.postprocessing_tools.metric_registry import register_metric
from physicsnemo.mesh.calculus.measure import cell_measures

from train_aero.folds import family_of, fold_summary, geometry_of
from train_aero.matching import is_one_to_one, match, to_truth_order
from train_aero.paths import layout
from train_aero.physics import integrate_moments, load_truth, outward_normals

RECIPE = layout().recipe
if str(RECIPE / "src") not in sys.path:      # recipe modules: datasets, infer, nondim, ...
    sys.path.insert(0, str(RECIPE / "src"))

_GEOMETRY_CACHE: dict[str, dict[str, Any]] = {}


def truth_geometry(family: str, case_id: str) -> dict[str, Any]:
    """Curated surface of a case: Cp, Cf, outward normals, areas, centroids (metres)."""
    if case_id not in _GEOMETRY_CACHE:
        surf, a_ref, cp, cf = load_truth(layout().base_dataset(family) / case_id / "domain.pdmsh")
        _GEOMETRY_CACHE[case_id] = {
            "surf": surf, "a_ref": a_ref, "cp": cp, "cf": cf, "n": outward_normals(surf),
            "a": cell_measures(surf).double(), "c": surf.cell_centroids.double()}
    return _GEOMETRY_CACHE[case_id]


def surface_polydata(g: dict[str, Any]) -> pv.PolyData:
    """Curated surface as PolyData.  Keeps the curated cell ordering (see module docstring)."""
    pts = g["surf"].points.double().numpy()
    cells = g["surf"].cells.long().numpy()
    mesh = pv.PolyData(pts, np.hstack([np.full((len(cells), 1), cells.shape[1]), cells]).ravel())
    mesh.cell_data["Cp"] = g["cp"].numpy()
    mesh.cell_data["Cf"] = g["cf"].numpy()
    return mesh


class TrainAeroAdapter(DatasetAdapter):
    """Test cases of one fold.  kwargs: fold (n1..n5, l1..l3); `root` caches the truth VTPs."""

    def __init__(self, root: str, fold: str, **kwargs: object) -> None:
        self.root, self.fold, self.family = Path(root), fold, family_of(fold)
        geometries = fold_summary()[fold]["test_geometries"]
        self.cases = sorted(d.name for d in layout().base_dataset(self.family).iterdir()
                            if d.is_dir() and geometry_of(d.name) in geometries)

    @classmethod
    def inference_domain(cls):
        return "surface"

    def list_cases(self) -> list[str]:
        return list(self.cases)

    def load_case(self, case_id: str) -> CanonicalCase:
        g = truth_geometry(self.family, case_id)
        vtp = self.root / self.family / f"{case_id}.vtp"
        if vtp.exists():
            mesh = pv.read(str(vtp))
        else:
            mesh = surface_polydata(g)
            vtp.parent.mkdir(parents=True, exist_ok=True)
            mesh.save(str(vtp))
        return CanonicalCase(
            case_id=case_id, mesh_path=str(vtp), mesh_type="cell",
            ground_truth={"pressure": g["cp"].numpy().astype(np.float32),
                          "shear_stress": g["cf"].numpy().astype(np.float32)},
            metadata={"fold": self.fold, "family": self.family, "A_ref": g["a_ref"],
                      "yaw_deg": int(re.search(r"yaw(\d+)", case_id).group(1)),
                      "geometry": geometry_of(case_id)},
            inference_domain="surface", reference_geometry=mesh)


class RecipeSurfaceWrapper(CFDModel):
    """GeoTransolver / AB-UPT / SMART trained with the unified recipe.

    load(checkpoint_path=<run>/train/checkpoints, stats_path=<fold norm_stats.json>, device,
         recipe_config=<run>/bench_infer_config.yaml, family=noses|lengths)
    """

    INFERENCE_DOMAIN: ClassVar = "surface"
    OUTPUT_LOCATION: ClassVar = "cell"
    REQUIRES_REMOTE_ASSETS: ClassVar[bool] = False

    @property
    def output_location(self):
        return self.OUTPUT_LOCATION

    def load(self, checkpoint_path: str, stats_path: str, device: str, **kwargs: Any):
        import hydra
        from datasets import apply_model_config, build_dataloaders, load_dataset_config
        from infer import build_redim_field_types
        from nondim import NonDimensionalizeByMetadata
        from omegaconf import OmegaConf
        from output_normalize import require_output_type, resolve_output_layout
        from physicsnemo.distributed import DistributedManager
        from physicsnemo.utils import load_checkpoint
        from utils import set_seed

        if not DistributedManager.is_initialized():
            DistributedManager.initialize()
        self.family = kwargs["family"]
        self.device = torch.device(device)
        cfg = OmegaConf.load(kwargs["recipe_config"])
        set_seed(cfg.training.get("seed", None), rank=0)
        _, val_loader, self.normalizer, info = build_dataloaders(cfg)
        self.target_config, self.target_sources = info["targets"], info["target_sources"]
        self.output_type = require_output_type(cfg)
        self.output_layout = resolve_output_layout(cfg)
        self.model = hydra.utils.instantiate(cfg.model, _convert_="partial").to(self.device)
        self.epoch = load_checkpoint(path=checkpoint_path, models=self.model, device=self.device)
        if self.epoch == 0:
            raise FileNotFoundError(f"no checkpoint restored from {checkpoint_path}")
        self.model.eval()
        self.n_params = sum(p.numel() for p in self.model.parameters())
        ds_yaml = apply_model_config(load_dataset_config(RECIPE / "datasets" / f"{cfg.dataset}.yaml"), cfg)
        self.field_types = build_redim_field_types(ds_yaml)
        self.nondim = NonDimensionalizeByMetadata(fields=self.field_types) if self.field_types else None
        self.dataset, self.collate_fn = val_loader.dataset, val_loader.collate_fn
        self.index = {}                                   # case_id -> dataset index
        for idx in val_loader.sampler:
            _, meta = self.dataset[idx]
            parts = Path(meta["source_path"]).parts
            name = next(p for p in parts[::-1] if p.startswith(("nose_", "train_")) and "_yaw" in p)
            self.index[name] = idx
        return self

    def prepare_inputs(self, case: CanonicalCase):
        sample = self.dataset[self.index[case.case_id]]
        batch = self.collate_fn([sample])
        try:
            from utils import recursive_to_device
        except ImportError:
            from physicsnemo.utils import recursive_to_device
        return sample[0], recursive_to_device(batch, self.device)

    def predict(self, model_input):
        from output_normalize import normalize_output_to_tensordict

        _, batch = model_input
        with torch.no_grad():
            out = self.model(**batch["forward_kwargs"])
        return normalize_output_to_tensordict(out, self.target_config, self.output_type,
                                              targets=batch["targets"], **self.output_layout)

    def decode_outputs(self, raw_output, case: CanonicalCase, model_input: Any | None = None):
        from infer import _to_pointwise, redimensionalize

        domain, _ = model_input
        pred = redimensionalize(_to_pointwise(raw_output, self.output_type), normalizer=self.normalizer,
                                nondim=self.nondim, field_types=self.field_types,
                                global_data=domain.global_data, target_sources=self.target_sources)
        g = truth_geometry(self.family, case.case_id)
        gd = domain.global_data
        q = float(0.5 * gd["rho_inf"].double() * gd["U_inf"].double().pow(2).sum())
        pts = domain.interior.points.double().cpu() * float(gd["L_ref"])
        pts = pts + (g["c"].amin(0) - pts.amin(0))        # undo CenterMesh (translation only)
        idx, dist = match(pts, g["c"])
        n = g["c"].shape[0]
        if pts.shape[0] != n or not is_one_to_one(idx, dist, n):
            raise RuntimeError(f"{case.case_id}: model points do not map one-to-one onto the truth cells")
        cp = to_truth_order(pred["pressure"].reshape(-1), idx, n) / q
        cf = to_truth_order(pred["wss"].reshape(-1, 3), idx, n) / q
        return build_predictions_dict(pressure=cp.numpy(), shear_stress=cf.numpy())


def _moment_metric(key: str, ground_truth: dict, predictions: dict, *, case: Any = None, **_: object):
    g = truth_geometry(case.metadata["family"], case.case_id)

    def moment(fields):
        cp = torch.as_tensor(np.asarray(fields["pressure"]), dtype=torch.float64)
        cf = torch.as_tensor(np.asarray(fields["shear_stress"]), dtype=torch.float64)
        return integrate_moments(cp, cf, g["a_ref"], g["c"], g["n"], g["a"])[key]

    t, p = moment(ground_truth), moment(predictions)
    return {"error": abs(p - t) / max(abs(t), 1e-6), "true": t, "pred": p}


register_adapter("train_aero", TrainAeroAdapter)
register_model("recipe_surface", RecipeSurfaceWrapper)
register_metric("side_force", functools.partial(lift_error, lift_direction=[0.0, 1.0, 0.0]), domain="surface")
register_metric("roll_moment", functools.partial(_moment_metric, "C_Mx"), domain="surface")
register_metric("roll_moment_lee", functools.partial(_moment_metric, "C_Mx_lee"), domain="surface")
