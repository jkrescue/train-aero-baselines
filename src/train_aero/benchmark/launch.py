"""Run the official PhysicsNeMo-CFD benchmark entry point with the train_aero plugin loaded.

    python -m train_aero.benchmark.launch --config-path=<abs dir> --config-name=train_aero_n2 [overrides]

`workflows/benchmarking/main.py` is executed unmodified (runpy, as __main__).  The only
addition is importing `train_aero.benchmark.plugin` first so its adapter, model and metrics
are registered, which is the extension route the benchmark README describes.
"""
from __future__ import annotations

import runpy
import sys

import train_aero.benchmark.plugin  # noqa: F401  (registers train_aero / recipe_surface / metrics)
from train_aero.paths import layout


def main() -> None:
    entry = layout().benchmark_main
    sys.argv[0] = str(entry)
    runpy.run_path(str(entry), run_name="__main__")


if __name__ == "__main__":
    main()
