"""Copy the curated datasets into the work directory and add one global field, U_hat.

    python -m train_aero.data.prepare

U_hat = U_inf / |U_inf| is the unit freestream direction.  All three models are conditioned
on the freestream; the raw vector is (111.11, 0..23.6, 0) m/s, and SMART's parameter
modulation has no input scaling (its loss oscillated by an order of magnitude with it).
The unit direction is the non-dimensional form of the same information (|U_inf| is constant
in this data and already used to form Cp / Cf), so every model gets the same O(1) input.
Nothing else in the files changes; the source datasets are not modified.
"""
from __future__ import annotations

import torch
from physicsnemo.mesh.domain_mesh import DomainMesh

from train_aero.paths import _require, layout

DATASETS = ("train_noses", "train_noses_shuffled", "train_lengths", "train_lengths_shuffled")


def add_unit_freestream(src, dst) -> DomainMesh:
    dm = DomainMesh.load(str(src))
    gd = dm.global_data.clone()
    gd["U_hat"] = gd["U_inf"] / gd["U_inf"].norm()
    DomainMesh(interior=dm.interior, boundaries=dm.boundaries, global_data=gd).save(str(dst))

    # the copy must be identical apart from the new field
    chk = DomainMesh.load(str(dst))
    v0, v1 = dm.boundaries["vehicle"], chk.boundaries["vehicle"]
    assert torch.equal(v0.points, v1.points) and torch.equal(v0.cells, v1.cells)
    for k in v0.cell_data.keys():
        assert torch.equal(v0.cell_data[k], v1.cell_data[k]), k
    for k in dm.global_data.keys():
        assert torch.equal(dm.global_data[k], chk.global_data[k]), k
    return chk


def main() -> None:
    lay = layout()
    source = _require(lay.source_data, "TRAIN_AERO_SOURCE_DATA")
    for name in DATASETS:
        dst_root = lay.data / "base" / name
        cases = sorted(p for p in (source / name).iterdir() if (p / "domain.pdmsh").exists())
        for case in cases:
            out = dst_root / case.name / "domain.pdmsh"
            if out.exists():
                continue
            out.parent.mkdir(parents=True, exist_ok=True)
            add_unit_freestream(case / "domain.pdmsh", out)
        print(f"{name}: {len(cases)} cases -> {dst_root}")


if __name__ == "__main__":
    main()
