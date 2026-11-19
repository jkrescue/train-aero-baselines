"""Study definition: geometry families, leave-geometry-out folds and model names."""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from train_aero.paths import CONFIG_DIR

NOSE_GEOMETRIES = [
    "nose_k060_ap00", "nose_k080_ap00", "nose_k100_am50", "nose_k100_am25", "nose_k100_ap00",
    "nose_k100_ap25", "nose_k100_ap50", "nose_k130_ap00", "nose_k160_ap00",
]
LENGTH_GEOMETRIES = ["train_L52", "train_L77", "train_L102", "train_L127", "train_L152"]

# Every geometry of a fold's test set is held out with ALL of its yaw angles.
FOLDS: dict[str, dict[str, Any]] = {
    # nose family: each of the nine geometries is tested exactly once across n1..n5
    "n1": {"family": "noses", "test": ["nose_k060_ap00", "nose_k100_am25"]},
    "n2": {"family": "noses", "test": ["nose_k080_ap00", "nose_k100_ap25"]},  # also LR-tuning fold
    "n3": {"family": "noses", "test": ["nose_k130_ap00", "nose_k100_am50"]},
    "n4": {"family": "noses", "test": ["nose_k160_ap00", "nose_k100_ap50"]},
    "n5": {"family": "noses", "test": ["nose_k100_ap00"]},
    # formation-length family
    "l1": {"family": "lengths", "test": ["train_L77"]},
    "l2": {"family": "lengths", "test": ["train_L127"]},
    "l3": {"family": "lengths", "test": ["train_L152"]},
}

def validation_case(fold: str) -> str:
    """Single validation case per fold: monitoring only, never used for checkpoint selection."""
    spec = FOLDS[fold]
    if spec["family"] == "lengths":
        return "train_L102_yaw03"
    geometry = "nose_k080_ap00" if "nose_k130_ap00" in spec["test"] else "nose_k130_ap00"
    return geometry + "_yaw06"


# short id (used in run paths) -> display name
MODELS = {
    "gt": "GeoTransolver",
    "smart": "SMART",
    "abupt": "AB-UPT",
}

A_REF_M2 = 11.0888          # frontal reference area of every geometry
FULL_MESH_SAMPLING = 10_000_000   # sampling_resolution larger than any mesh -> all cells


def family_of(fold: str) -> str:
    return FOLDS[fold]["family"]


def geometry_of(case_id: str) -> str:
    """`nose_k080_ap00_yaw06` -> `nose_k080_ap00`."""
    return case_id.rsplit("_yaw", 1)[0]


def recipe_model_config(model: str, family: str) -> str:
    return {"gt": "ev_geotransolver", "smart": f"ev_smart_{family}", "abupt": "ev_ab_upt"}[model]


def default_dataset_suffix(model: str) -> str:
    """AB-UPT reads point sets (`_ps`); the other two read the mesh dataset."""
    return "_ps" if model == "abupt" else ""


@lru_cache(maxsize=1)
def fold_summary() -> dict[str, Any]:
    """`configs/folds.json`, written by `train_aero.data.make_folds` (test geometries, sizes, wss std)."""
    return json.loads((CONFIG_DIR / "folds.json").read_text())
