"""Surface-field scoring shared by every model: field errors, forces and EN 14067-6 moments.

Convention (validated against OpenFOAM `forceCoeffs`): traction t = -Cp * n_out - Cf,
C_F = (1 / A_ref) * sum_cells t * area  (the P0 cell rule `Mesh.integrate` applies).
"""
from __future__ import annotations

from pathlib import Path

import torch
from physicsnemo.mesh.calculus.measure import cell_measures
from physicsnemo.mesh.domain_mesh import DomainMesh

# EN 14067-6 reference quantities for the rolling-moment coefficients.  h_ref and b0 only set
# the normalisation; relative errors of C_Mx do not depend on them, C_Mx_lee only via b0 / h_ref.
H_REF_M = 3.0      # reference height
B0_M = 0.75        # half the standard 1.435 m track gauge, rounded as in the standard


def field_metrics(pred: torch.Tensor, true: torch.Tensor, name: str) -> dict[str, float]:
    pred, true = pred.double().reshape(true.shape), true.double()
    err = pred - true
    return {
        f"{name}_mae": float(err.abs().mean()),
        f"{name}_rmse": float(err.pow(2).mean().sqrt()),
        f"{name}_rel_l2": float(err.norm() / true.norm()) if float(true.norm()) else float("nan"),
    }


def outward_normals(surf) -> torch.Tensor:
    """Cell normals oriented outward (sign fixed with the divergence theorem)."""
    n = surf.cell_normals.double()
    c = surf.cell_centroids.double()
    a = cell_measures(surf).double()
    return n * (1.0 if float((c * n).sum(-1).mul(a).sum()) > 0 else -1.0)


def integrate_forces(cp, cf, a_ref, normals, areas) -> dict[str, float]:
    a = areas.double().reshape(-1, 1)
    fp = (-cp.double().reshape(-1, 1) * normals.double() * a).sum(0) / a_ref
    fv = (-cf.double().reshape(-1, 3) * a).sum(0) / a_ref
    f = fp + fv
    return {"Cd_x": float(f[0]), "Cs_y": float(f[1]), "Cl_z": float(f[2]),
            "Cd_x_pressure": float(fp[0]), "Cd_x_viscous": float(fv[0])}


def integrate_moments(cp, cf, a_ref, centroids, normals, areas, h_ref=H_REF_M, b0=B0_M) -> dict[str, float]:
    """Moment coefficients about the track centre line at rail level, reference point (x_mid, 0, 0).

    `centroids` must be in metres with z measured from the rail and y from the track centre.
    C_Mx_lee = C_Mx + C_Lz * b0 / h_ref is the EN 14067-6 overturning moment about the lee rail;
    it mixes side force and lift and is what crosswind safety is assessed on.
    """
    a = areas.double().reshape(-1, 1)
    r = centroids.double().reshape(-1, 3).clone()
    r[:, 0] -= r[:, 0].mean()
    t = -cp.double().reshape(-1, 1) * normals.double() - cf.double().reshape(-1, 3)
    m = torch.cross(r, t, dim=-1).mul(a).sum(0) / (a_ref * h_ref)
    f = (t * a).sum(0) / a_ref
    return {"C_Mx": float(m[0]), "C_My": float(m[1]), "C_Mz": float(m[2]),
            "C_Mx_lee": float(m[0] + f[2] * b0 / h_ref), "h_ref_m": h_ref, "b0_m": b0}


def _rel(p: float, t: float, floor: float = 1e-6) -> float:
    """Relative error guarded against coefficients that pass through zero across a yaw sweep."""
    return abs(p - t) / max(abs(t), floor)


def score(a_ref, cp_p, cf_p, cp_t, cf_t, normals, areas, centroids=None) -> dict:
    """Field metrics, integrated forces and (with centroids) moments for one case."""
    res = {}
    res.update(field_metrics(cp_p, cp_t, "Cp"))
    for i, ax in enumerate("xyz"):
        res.update(field_metrics(cf_p[:, i], cf_t[:, i], f"Cf{ax}"))
    res.update(field_metrics(cf_p, cf_t, "Cf"))

    pf = integrate_forces(cp_p, cf_p, a_ref, normals, areas)
    tf = integrate_forces(cp_t, cf_t, a_ref, normals, areas)
    res["forces_pred"], res["forces_true"] = pf, tf
    res["Cd_x_rel_err"] = abs(pf["Cd_x"] - tf["Cd_x"]) / abs(tf["Cd_x"])
    res["Cs_y_rel_err"] = _rel(pf["Cs_y"], tf["Cs_y"])
    res["Cl_z_rel_err"] = _rel(pf["Cl_z"], tf["Cl_z"])
    # a side force with the wrong sign points the train over the other rail: report it separately
    res["Cs_y_sign_ok"] = bool(pf["Cs_y"] * tf["Cs_y"] > 0)

    if centroids is not None:
        pm = integrate_moments(cp_p, cf_p, a_ref, centroids, normals, areas)
        tm = integrate_moments(cp_t, cf_t, a_ref, centroids, normals, areas)
        res["moments_pred"], res["moments_true"] = pm, tm
        for k in ("C_Mx", "C_Mz", "C_Mx_lee"):
            res[f"{k}_rel_err"] = _rel(pm[k], tm[k])
            res[f"{k}_sign_ok"] = bool(pm[k] * tm[k] > 0)
    return res


def load_truth(pdmsh: Path):
    """Reference surface, A_ref, Cp and Cf (cell data) straight from a curated case."""
    dm = DomainMesh.load(str(pdmsh))
    surf, gd = dm.boundaries["vehicle"], dm.global_data
    q = 0.5 * gd["rho_inf"].double() * gd["U_inf"].double().pow(2).sum()
    cp = (surf.cell_data["p"].double() - gd["p_inf"].double()) / q
    cf = surf.cell_data["wallShearStress"].double() / q
    return surf, float(gd["A_ref"]), cp, cf
