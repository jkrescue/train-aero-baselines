"""Force convention on the sample case (requires physicsnemo)."""
import pytest

pytest.importorskip("physicsnemo.mesh")
pytestmark = pytest.mark.physicsnemo

from train_aero.physics import integrate_forces, load_truth, outward_normals  # noqa: E402

# OpenFOAM-validated coefficients of nose_k080_ap00_yaw06 (docs/report.md section 3.3)
EXPECTED = {"Cd_x": 0.22341, "Cs_y": 0.53385, "Cl_z": 0.16958}


@pytest.fixture(scope="module")
def truth(sample_case):
    from physicsnemo.mesh.calculus.measure import cell_measures

    surf, a_ref, cp, cf = load_truth(sample_case)
    return surf, a_ref, cp, cf, outward_normals(surf), cell_measures(surf).double()


def test_integrated_forces_match_reference(truth):
    _, a_ref, cp, cf, n, a = truth
    f = integrate_forces(cp, cf, a_ref, n, a)
    for k, v in EXPECTED.items():
        assert f[k] == pytest.approx(v, abs=5e-6), k


def test_benchmark_force_convention(truth):
    """PhysicsNeMo-CFD's compute_drag_and_lift on the curated cell ordering equals our convention."""
    aero = pytest.importorskip("physicsnemo.cfd.postprocessing_tools.metrics.aero_forces")
    import numpy as np
    import pyvista as pv

    surf, a_ref, cp, cf, _, _ = truth
    cells = surf.cells.long().numpy()
    mesh = pv.PolyData(surf.points.double().numpy(),
                       np.hstack([np.full((len(cells), 1), cells.shape[1]), cells]).ravel())
    mesh.cell_data["p"], mesh.cell_data["wss"] = cp.numpy(), cf.numpy()
    for direction, key in (([1, 0, 0], "Cd_x"), ([0, 1, 0], "Cs_y"), ([0, 0, 1], "Cl_z")):
        res = aero.compute_drag_and_lift(mesh, coeff=1.0 / a_ref, drag_direction=direction,
                                         lift_direction=direction, dtype="cell")
        assert float(res[0]) == pytest.approx(EXPECTED[key], abs=5e-6), key
