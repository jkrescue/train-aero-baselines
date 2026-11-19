"""No-learning control baselines for the NOSE-SHAPE dataset.

`train_aero.baselines.length` cannot be reused here, and that is the point.  Its two
strong baselines both lean on the body length:

  * `linear_in_length` fits each force coefficient against L
  * `nearest_geometry_warp` picks the training geometry closest in L and maps
    its field across in LENGTH-NORMALISED coordinates (x/L, y, z)

Every geometry in this family is 101.912 m long with the same 11.0887 m^2
frontal area, so "closest in L" is a tie among all of them and dividing x by L
is the identity.  The baselines that have been beating every model since the
beginning simply have nothing left to work with.

What replaces them is the fairest available competitor for THIS family -- the
same idea, but with "nearest" measured in the space the geometries actually
differ in:

  * `nearest_shape_warp` -- take the training geometry closest in nose
    parameters (k = nose length factor, a = profile fullness), and carry its
    field across by nearest neighbour in RAW coordinates.  Since the two noses
    differ by at most a couple of metres of profile, this is a genuinely
    strong competitor, not a straw man.
  * `shape_interp_warp` -- the same, but linearly interpolating between the
    two nearest training shapes along the axis the test shape varies on.  This
    is what an engineer would actually do with a shape table.
  * `train_mean_warp` -- average every training geometry's field on the test
    mesh: the analogue of "just average the training set", which no model has
    beaten yet on the length family.
  * `global_mean_value` -- one constant everywhere; the floor.

Shape parameters are read from the case name (`nose_k080_am25_yaw06`), which
the geometry generator builds from the parameters themselves.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import torch
from physicsnemo.mesh.calculus.measure import cell_measures
from physicsnemo.mesh.domain_mesh import DomainMesh

from train_aero.physics import outward_normals

NAME_RE = re.compile(r"nose_k(\d{3})_a([mp])(\d{2})")


def shape_params(case: str) -> tuple[float, float]:
    """(k, a) out of the directory name; they are what the name encodes."""
    m = NAME_RE.match(case)
    if not m:
        raise SystemExit(f"cannot read nose parameters from {case!r}")
    k = int(m.group(1)) / 100.0
    a = int(m.group(3)) / 100.0 * (-1 if m.group(2) == "m" else 1)
    return k, a



def load(pdmsh: Path, case: str):
    dm = DomainMesh.load(str(pdmsh))
    s, gd = dm.boundaries["vehicle"], dm.global_data
    q = 0.5 * gd["rho_inf"].double() * gd["U_inf"].double().pow(2).sum()
    k, a = shape_params(case)
    return {
        "cp": (s.cell_data["p"].double() - gd["p_inf"].double()) / q,
        "cf": s.cell_data["wallShearStress"].double() / q,
        "centers": s.cell_centroids.double(),
        "areas": cell_measures(s).double(),
        "normals": outward_normals(s),
        "yaw": float(gd["yaw_deg"]), "A_ref": float(gd["A_ref"]),
        "L": float(gd["L_ref"]), "k": k, "a": a,
    }


def forces(d, cp, cf):
    t = -cp.reshape(-1, 1) * d["normals"] - cf.reshape(-1, 3)
    f = (t * d["areas"].reshape(-1, 1)).sum(0) / d["A_ref"]
    return {"Cd_x": float(f[0]), "Cs_y": float(f[1]), "Cl_z": float(f[2])}


def rel_l2(p, t):
    return float((p - t).norm() / t.norm())


def warp(src, dst):
    """Carry src's field onto dst's cells, nearest neighbour in raw metres.

    No coordinate normalisation: the geometries are already the same length,
    so normalising would be the identity -- stating that explicitly is the
    whole reason this dataset exists."""
    from scipy.spatial import cKDTree
    idx = cKDTree(src["centers"].numpy()).query(dst["centers"].numpy(), k=1)[1]
    idx = torch.from_numpy(idx.astype("int64"))
    return src["cp"][idx], src["cf"][idx]


def shape_distance(p, q) -> float:
    """Distance in nose-parameter space.

    k and a are on different scales, so each is divided by the spread the
    family actually covers (k: 0.6-1.6, a: -0.5-0.5) before combining."""
    return float(np.hypot((p["k"] - q["k"]) / 1.0, (p["a"] - q["a"]) / 1.0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    man = json.loads((args.dataset / "manifest.json").read_text())
    train = {r: load(args.dataset / r / "domain.pdmsh", r) for r in man["train"]}
    tests = {r: load(args.dataset / r / "domain.pdmsh", r) for r in man["test"]}

    shapes = sorted({(d["k"], d["a"]) for d in train.values()})
    print(f"training shapes (k, a): {shapes}")
    print(f"held-out shapes        : {sorted({(d['k'], d['a']) for d in tests.values()})}")
    lens = sorted({round(d["L"], 3) for d in {**train, **tests}.values()})
    print(f"lengths present        : {lens}   <- all equal, so every "
          f"length-based baseline is degenerate here\n")

    cp_all = torch.cat([d["cp"] for d in train.values()])
    cf_all = torch.cat([d["cf"] for d in train.values()], 0)
    cp_mean, cf_mean = cp_all.mean(), cf_all.mean(0)

    report = {"training_shapes": shapes, "lengths": lens, "cases": {}}
    for name, t in tests.items():
        same_yaw = [kv for kv in train.items() if abs(kv[1]["yaw"] - t["yaw"]) < 1e-6]
        if not same_yaw:
            print(f"{name}: no training case at this yaw, skipping")
            continue
        true_f = forces(t, t["cp"], t["cf"])
        rec = {"yaw": t["yaw"], "k": t["k"], "a": t["a"],
               "forces_true": true_f, "baselines": {}}

        ordered = sorted(same_yaw, key=lambda kv: shape_distance(kv[1], t))

        # --- nearest shape ---------------------------------------------------
        near = ordered[0]
        cp_w, cf_w = warp(near[1], t)
        rec["baselines"]["nearest_shape_warp"] = {
            "source": near[0], "shape_distance": shape_distance(near[1], t),
            "Cp_rel_l2": rel_l2(cp_w, t["cp"]), "Cf_rel_l2": rel_l2(cf_w, t["cf"]),
            "forces": forces(t, cp_w, cf_w)}

        # --- linear blend of the two nearest ---------------------------------
        if len(ordered) >= 2:
            (n1, d1), (n2, d2) = ordered[0], ordered[1]
            w1 = shape_distance(d1, t)
            w2 = shape_distance(d2, t)
            ### Inverse-distance weights, guarded in case the test shape
            ### coincides with a training one (it should not, but a zero
            ### distance would otherwise divide by zero).
            if w1 < 1e-9:
                al = 1.0
            else:
                al = (1.0 / w1) / (1.0 / w1 + 1.0 / max(w2, 1e-9))
            c1p, c1f = warp(d1, t)
            c2p, c2f = warp(d2, t)
            cp_b, cf_b = al * c1p + (1 - al) * c2p, al * c1f + (1 - al) * c2f
            rec["baselines"]["shape_interp_warp"] = {
                "sources": [n1, n2], "weight_first": al,
                "Cp_rel_l2": rel_l2(cp_b, t["cp"]), "Cf_rel_l2": rel_l2(cf_b, t["cf"]),
                "forces": forces(t, cp_b, cf_b)}

        # --- mean of every training geometry at this yaw ----------------------
        ws = [warp(d, t) for _, d in same_yaw]
        cp_m = torch.stack([w[0] for w in ws]).mean(0)
        cf_m = torch.stack([w[1] for w in ws]).mean(0)
        rec["baselines"]["train_mean_warp"] = {
            "n_sources": len(ws),
            "Cp_rel_l2": rel_l2(cp_m, t["cp"]), "Cf_rel_l2": rel_l2(cf_m, t["cf"]),
            "forces": forces(t, cp_m, cf_m)}

        rec["baselines"]["global_mean_value"] = {
            "Cp_rel_l2": rel_l2(torch.full_like(t["cp"], float(cp_mean)), t["cp"]),
            "Cf_rel_l2": rel_l2(cf_mean.expand_as(t["cf"]), t["cf"])}

        report["cases"][name] = rec

        print(f"{name}  (k={t['k']:.2f}, a={t['a']:+.2f}, yaw {t['yaw']:.0f})")
        print(f"  true                   Cd_x={true_f['Cd_x']:+.4f} "
              f"Cs_y={true_f['Cs_y']:+.4f} Cl_z={true_f['Cl_z']:+.4f}")
        for bname, b in rec["baselines"].items():
            line = f"  {bname:22s} Cp_relL2={b['Cp_rel_l2']:.4f} Cf_relL2={b['Cf_rel_l2']:.4f}"
            if "forces" in b:
                for key in ("Cd_x", "Cs_y"):
                    e = abs(b["forces"][key] - true_f[key]) / max(abs(true_f[key]), 1e-9) * 100
                    line += f" {key}={b['forces'][key]:+.4f}({e:.0f}%)"
            print(line)
        print()

    if report["cases"]:
        best = {}
        for b in ("nearest_shape_warp", "shape_interp_warp", "train_mean_warp",
                  "global_mean_value"):
            vals = [c["baselines"][b]["Cp_rel_l2"] for c in report["cases"].values()
                    if b in c["baselines"]]
            if vals:
                best[b] = float(np.mean(vals))
        report["mean_Cp_rel_l2"] = best
        print("averaged over the held-out cases (Cp relL2) -- "
              "THIS is the number a model has to beat:")
        for b, v in sorted(best.items(), key=lambda kv: kv[1]):
            print(f"  {b:22s} {v:.4f}")

    if args.out:
        args.out.write_text(json.dumps(report, indent=2))
        print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
