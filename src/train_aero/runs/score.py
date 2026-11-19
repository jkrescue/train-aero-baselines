"""Independent cross-check: score the predictions written by the recipe's own `src/infer.py`.

    python -m train_aero.runs.score [--force]

For every finished run, each `infer/train/predictions/*.pdmsh` is mapped back onto the
curated ground-truth mesh by position (one-to-one, < 1 mm) and scored with
`train_aero.physics.score`.  The Cp relative L2 must equal the benchmark's `l2_pressure`.
Two consistency checks per case:
  truth_roundtrip_*   infer.py's own `true_*` fields, mapped the same way, must reproduce the
                      curated Cp / Cf; a unit, normalisation or ordering mistake shows up here.
  match_max_dist_m    worst centroid mismatch after undoing L_ref and centring.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from physicsnemo.mesh.calculus.measure import cell_measures
from physicsnemo.mesh.domain_mesh import DomainMesh

from train_aero.matching import is_one_to_one, match, to_truth_order
from train_aero.paths import layout
from train_aero.physics import load_truth, outward_normals, score

_TRUTH: dict[tuple[str, str], dict] = {}


def truth(family: str, case: str) -> dict:
    if (family, case) not in _TRUTH:
        surf, a_ref, cp, cf = load_truth(layout().base_dataset(family) / case / "domain.pdmsh")
        _TRUTH[family, case] = {"a_ref": a_ref, "cp": cp, "cf": cf, "n": outward_normals(surf),
                                "a": cell_measures(surf).double(), "c": surf.cell_centroids.double()}
    return _TRUTH[family, case]


def score_case(pred_path: Path, family: str) -> dict:
    case = pred_path.name.split("_", 1)[1].rsplit("_domain", 1)[0]
    t = truth(family, case)
    dm = DomainMesh.load(str(pred_path))
    gd, pd = dm.global_data, dm.interior.point_data
    q = float(0.5 * gd["rho_inf"].double() * gd["U_inf"].double().pow(2).sum())
    pts = dm.interior.points.double() * float(gd["L_ref"])
    pts = pts + (t["c"].amin(0) - pts.amin(0))
    idx, dist = match(pts, t["c"])
    n = t["c"].shape[0]
    cp_p = to_truth_order(pd["pred_pressure"].reshape(-1), idx, n) / q
    cf_p = to_truth_order(pd["pred_wss"], idx, n) / q
    cp_t = to_truth_order(pd["true_pressure"].reshape(-1), idx, n) / q
    cf_t = to_truth_order(pd["true_wss"], idx, n) / q
    res = score(t["a_ref"], cp_p, cf_p, t["cp"], t["cf"], t["n"], t["a"], centroids=t["c"])
    res.update(case=case, n_cells=n, n_pred=int(pts.shape[0]),
               one_to_one=pts.shape[0] == n and is_one_to_one(idx, dist, n, tol=float("inf")),
               match_max_dist_m=float(dist.max()),
               truth_roundtrip_cp=float((cp_t - t["cp"]).norm() / t["cp"].norm()),
               truth_roundtrip_cf=float((cf_t - t["cf"]).norm() / t["cf"].norm()))
    return res


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", type=Path, default=layout().runs)
    ap.add_argument("--force", action="store_true", help="re-score runs that already have score.json")
    args = ap.parse_args()
    for rj in sorted(args.root.rglob("run.json")):
        run, out = rj.parent, rj.parent / "score.json"
        if out.exists() and not args.force:
            continue
        preds = sorted((run / "infer/train/predictions").glob("*.pdmsh"))
        if not preds:
            print("no predictions:", run)
            continue
        meta = json.loads(rj.read_text())
        cases = [score_case(p, meta["family"]) for p in preds]
        out.write_text(json.dumps({"meta": meta, "cases": cases}, indent=1))
        cp = sum(c["Cp_rel_l2"] for c in cases) / len(cases)
        cf = sum(c["Cf_rel_l2"] for c in cases) / len(cases)
        print(f"{run}  Cp={cp:.4f}  Cf={cf:.4f}  "
              f"roundtrip={max(c['truth_roundtrip_cp'] for c in cases):.1e}/"
              f"{max(c['truth_roundtrip_cf'] for c in cases):.1e}  "
              f"1to1={all(c['one_to_one'] for c in cases)}  "
              f"maxdist={max(c['match_max_dist_m'] for c in cases):.1e}")


if __name__ == "__main__":
    main()
