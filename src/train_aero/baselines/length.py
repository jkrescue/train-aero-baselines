"""No-learning control baselines for the multi-geometry (formation-length) dataset.

The single-geometry baselines do not transfer: with different body lengths the
meshes have different cell counts, so a per-cell mean is undefined.  That is
itself the point of adding geometry variation -- it kills the trivial average.

What replaces it, and what a model must beat:

  * `linear_in_length` -- least-squares fit of the integrated Cd against body
    length (per yaw angle) over the training geometries, extrapolated to the
    held-out one.  For a constant-frontal-area body whose wetted area grows
    linearly, this is the physically expected law, so it is a strong and very
    cheap competitor for the engineering quantity.
  * `nearest_geometry_warp` -- take the training geometry closest in length and
    carry its surface field onto the test geometry by nearest neighbour in
    LENGTH-NORMALISED coordinates (x/L, y, z).  Since these geometries are
    stretched versions of one another, this asks: does the model know anything
    beyond "the field scales with the body"?
  * `global_mean_value` -- predict the scalar training mean everywhere.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from physicsnemo.mesh.calculus.measure import cell_measures
from physicsnemo.mesh.domain_mesh import DomainMesh

from train_aero.physics import outward_normals


def load(pdmsh: Path):
    dm = DomainMesh.load(str(pdmsh))
    s, gd = dm.boundaries["vehicle"], dm.global_data
    q = 0.5 * gd["rho_inf"].double() * gd["U_inf"].double().pow(2).sum()
    return {
        "mesh": s,
        "cp": (s.cell_data["p"].double() - gd["p_inf"].double()) / q,
        "cf": s.cell_data["wallShearStress"].double() / q,
        "centers": s.cell_centroids.double(),
        "areas": cell_measures(s).double(),
        "normals": outward_normals(s),
        "L": float(gd["L_ref"]), "yaw": float(gd["yaw_deg"]),
        "A_ref": float(gd["A_ref"]),
    }



def forces(d, cp, cf):
    t = -cp.reshape(-1, 1) * d["normals"] - cf.reshape(-1, 3)
    f = (t * d["areas"].reshape(-1, 1)).sum(0) / d["A_ref"]
    return {"Cd_x": float(f[0]), "Cs_y": float(f[1]), "Cl_z": float(f[2])}


def rel_l2(p, t):
    return float((p - t).norm() / t.norm())


def warp_transfer(src, dst):
    """Carry src's field onto dst's cells via nearest neighbour in (x/L, y, z)."""
    def norm_coords(d):
        c = d["centers"].clone()
        x0 = c[:, 0].min()
        c[:, 0] = (c[:, 0] - x0) / d["L"]
        return c
    a, b = norm_coords(src).numpy(), norm_coords(dst).numpy()
    # A KD-tree, not a dense cdist: these meshes have 10^5 cells each, so the
    # full distance matrix would be ~10^10 entries and the process gets killed.
    from scipy.spatial import cKDTree
    idx = torch.from_numpy(cKDTree(a).query(b, k=1)[1].astype("int64"))
    return src["cp"][idx], src["cf"][idx]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    man = json.loads((args.dataset / "manifest.json").read_text())
    train = {r: load(args.dataset / r / "domain.pdmsh") for r in man["train"]}
    tests = {r: load(args.dataset / r / "domain.pdmsh") for r in man["test"]}

    tr_L = sorted({round(d["L"], 2) for d in train.values()})
    print(f"training lengths: {tr_L}")
    print(f"held-out lengths: {sorted({round(d['L'],2) for d in tests.values()})}\n")

    cp_all = torch.cat([d["cp"] for d in train.values()])
    cf_all = torch.cat([d["cf"] for d in train.values()], 0)
    cp_mean, cf_mean = cp_all.mean(), cf_all.mean(0)

    report = {"training_lengths": tr_L, "cases": {}}
    for name, t in tests.items():
        true_f = forces(t, t["cp"], t["cf"])
        rec = {"yaw": t["yaw"], "L": t["L"], "forces_true": true_f, "baselines": {}}

        # --- linear in length, fitted at the same yaw ------------------------
        same = [(d["L"], forces(d, d["cp"], d["cf"])) for d in train.values()
                if abs(d["yaw"] - t["yaw"]) < 1e-6]
        if len(same) >= 2:
            L = np.array([s[0] for s in same])
            fit = {}
            for k in ("Cd_x", "Cs_y", "Cl_z"):
                y = np.array([s[1][k] for s in same])
                m, c = np.polyfit(L, y, 1)
                fit[k] = float(m * t["L"] + c)
            rec["baselines"]["linear_in_length"] = {
                "forces": fit, "n_points": len(same)}

        # --- nearest geometry, length-normalised warp ------------------------
        near = min(train.items(), key=lambda kv: (abs(kv[1]["L"] - t["L"]),
                                                  abs(kv[1]["yaw"] - t["yaw"])))
        same_yaw = [kv for kv in train.items() if abs(kv[1]["yaw"] - t["yaw"]) < 1e-6]
        if same_yaw:
            near = min(same_yaw, key=lambda kv: abs(kv[1]["L"] - t["L"]))
        cp_w, cf_w = warp_transfer(near[1], t)
        rec["baselines"]["nearest_geometry_warp"] = {
            "source": near[0], "source_L": near[1]["L"],
            "Cp_rel_l2": rel_l2(cp_w, t["cp"]), "Cf_rel_l2": rel_l2(cf_w, t["cf"]),
            "forces": forces(t, cp_w, cf_w)}

        # --- constant field --------------------------------------------------
        rec["baselines"]["global_mean_value"] = {
            "Cp_rel_l2": rel_l2(torch.full_like(t["cp"], float(cp_mean)), t["cp"]),
            "Cf_rel_l2": rel_l2(cf_mean.expand_as(t["cf"]), t["cf"])}

        report["cases"][name] = rec

        print(f"{name} (L={t['L']:.0f} m, yaw {t['yaw']:.0f})")
        print(f"  true                   Cd_x={true_f['Cd_x']:+.4f} "
              f"Cs_y={true_f['Cs_y']:+.4f} Cl_z={true_f['Cl_z']:+.4f}")
        for bname, b in rec["baselines"].items():
            line = f"  {bname:22s}"
            if "Cp_rel_l2" in b:
                line += f" Cp_relL2={b['Cp_rel_l2']:.4f} Cf_relL2={b['Cf_rel_l2']:.4f}"
            if "forces" in b:
                for k in ("Cd_x", "Cs_y", "Cl_z"):
                    e = abs(b["forces"][k] - true_f[k]) / max(abs(true_f[k]), 1e-9) * 100
                    line += f" {k}={b['forces'][k]:+.4f}({e:.0f}%)"
            print(line)
        print()

    if args.out:
        args.out.write_text(json.dumps(report, indent=2))
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
