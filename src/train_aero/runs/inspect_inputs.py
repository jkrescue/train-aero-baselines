"""Fairness gate: dump what each model actually receives for the same fold.

    python -m train_aero.runs.inspect_inputs [fold]      # default n2

Goes through the recipe's own `build_dataloaders` (no hand-rolled preprocessing) and writes
shape / min / max / mean / std of every forward-kwarg and target tensor of the first training
batch to `<workdir>/gates/inputs_<fold>.json`.  The target statistics must agree across models.
"""
from __future__ import annotations

import json
import os
import sys

import torch

from train_aero.folds import family_of, recipe_model_config
from train_aero.paths import layout


def describe(name: str, t, out: dict) -> None:
    from tensordict import TensorDict

    if isinstance(t, dict | TensorDict):
        for k in t.keys():
            describe(f"{name}.{k}", t[k], out)
    elif isinstance(t, list | tuple):
        for i, x in enumerate(t):
            describe(f"{name}[{i}]", x, out)
    elif torch.is_tensor(t):
        f = t.float()
        d = {"shape": list(t.shape)}
        if t.numel() <= 6:
            d["values"] = [round(v, 5) for v in f.flatten().tolist()]
        else:
            flat = f.reshape(-1, f.shape[-1]) if f.dim() > 1 else f.reshape(-1, 1)
            d.update(min=[round(v, 4) for v in flat.min(0).values.tolist()],
                     max=[round(v, 4) for v in flat.max(0).values.tolist()],
                     mean=[round(v, 4) for v in flat.mean(0).tolist()],
                     std=[round(v, 4) for v in flat.std(0).tolist()])
        out[name] = d


def main() -> None:
    lay = layout()
    sys.path.insert(0, str(lay.recipe / "src"))
    os.chdir(lay.recipe)
    from datasets import build_dataloaders
    from hydra import compose, initialize_config_dir
    from physicsnemo.distributed import DistributedManager

    DistributedManager.initialize()
    fold = sys.argv[1] if len(sys.argv) > 1 else "n2"
    family = family_of(fold)
    result = {}
    for model, dataset in ((recipe_model_config("gt", family), f"ev_{fold}_shuf"),
                           (recipe_model_config("smart", family), f"ev_{fold}_shuf"),
                           (recipe_model_config("abupt", family), f"ev_{fold}_shuf_ps")):
        with initialize_config_dir(config_dir=str(lay.recipe / "conf"), version_base=None):
            cfg = compose("train", overrides=[f"model={model}", f"dataset={dataset}", "sampling_resolution=32000",
                                              "compile=false", "precision=float32", "training.seed=0"])
        train_loader, val_loader, _, _ = build_dataloaders(cfg)
        out = {"n_train": len(train_loader), "n_val": len(val_loader)}
        batch = next(iter(train_loader))
        describe("fk", batch["forward_kwargs"], out)
        describe("targets", batch["targets"], out)
        result[model] = out
        print("=====", model, dataset)
        for k, v in out.items():
            print("  ", k, v)
    (lay.workdir / "gates").mkdir(parents=True, exist_ok=True)
    (lay.workdir / "gates" / f"inputs_{fold}.json").write_text(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
