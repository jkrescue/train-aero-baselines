"""Filesystem layout of a study.

Code and configs live in this repository; data, checkpoints and benchmark outputs
live in a separate *work directory*.  Everything machine-specific is read from
environment variables (see `.env.example`):

    TRAIN_AERO_WORKDIR        work directory (default: <repo>/workdir)
    PHYSICSNEMO_ROOT          PhysicsNeMo checkout used for training (recipe source)
    PHYSICSNEMO_CFD_ROOT      PhysicsNeMo-CFD checkout used for the benchmark
    TRAIN_AERO_SOURCE_DATA    curated .pdmsh datasets (input of `train_aero.data.prepare`)

Work-directory layout::

    data/base/<dataset>/<case>/domain.pdmsh     curated cases + U_hat
    data/<fold>_{orig,shuf}/                    symlinks to base + manifest.json / norm_stats.json
    runs/<family>/<model>/<fold>/<run>/         one training run (see scripts/run_one.sh)
    bench/{conf,truth,results,logs}/            PhysicsNeMo-CFD benchmark inputs and outputs
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "configs"
RECIPE_SUBDIR = Path("examples/cfd/external_aerodynamics/unified_external_aero_recipe")
BENCHMARK_MAIN = Path("workflows/benchmarking/main.py")


def _env_path(name: str) -> Path | None:
    value = os.environ.get(name)
    return Path(value).expanduser().resolve() if value else None


def _require(path: Path | None, var: str) -> Path:
    if path is None:
        raise RuntimeError(f"environment variable {var} is not set (see .env.example)")
    return path


@dataclass(frozen=True)
class Layout:
    workdir: Path
    physicsnemo_root: Path | None
    physicsnemo_cfd_root: Path | None
    source_data: Path | None

    # ---- external checkouts ----------------------------------------------------
    @property
    def recipe(self) -> Path:
        """PhysicsNeMo unified external-aerodynamics recipe."""
        return _require(self.physicsnemo_root, "PHYSICSNEMO_ROOT") / RECIPE_SUBDIR

    @property
    def benchmark_main(self) -> Path:
        """Official PhysicsNeMo-CFD benchmark entry point."""
        return _require(self.physicsnemo_cfd_root, "PHYSICSNEMO_CFD_ROOT") / BENCHMARK_MAIN

    # ---- work directory -----------------------------------------------------------
    @property
    def data(self) -> Path:
        return self.workdir / "data"

    @property
    def runs(self) -> Path:
        return self.workdir / "runs"

    @property
    def bench(self) -> Path:
        return self.workdir / "bench"

    def base_dataset(self, family: str, shuffled: bool = False) -> Path:
        name = "train_noses" if family == "noses" else "train_lengths"
        return self.data / "base" / (name + ("_shuffled" if shuffled else ""))

    def fold_dir(self, fold: str, variant: str) -> Path:
        """`variant` is "orig" (curated cell order) or "shuf" (cells stored in random order)."""
        return self.data / f"{fold}_{variant}"


@lru_cache(maxsize=1)
def layout() -> Layout:
    return Layout(
        workdir=_env_path("TRAIN_AERO_WORKDIR") or REPO_ROOT / "workdir",
        physicsnemo_root=_env_path("PHYSICSNEMO_ROOT"),
        physicsnemo_cfd_root=_env_path("PHYSICSNEMO_CFD_ROOT"),
        source_data=_env_path("TRAIN_AERO_SOURCE_DATA"),
    )
