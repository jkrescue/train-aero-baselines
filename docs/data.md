# Data card

## Source

44 steady RANS cases of a generic high-speed train, computed with OpenFOAM `simpleFoam`
(k-ω SST) at 400 km/h (U∞ = 111.11 m/s), ground at z = 0. The surface fields are the
converged pressure and wall shear stress, multiplied by ρ during curation so they are in Pa.

| Family | Cases | Geometry variation | Operating condition |
|---|---|---|---|
| Nose shape (`train_noses`) | 27 | 9 nose profiles, same length (101.9 m) and frontal area | yaw 0° / 6° / 12° |
| Formation length (`train_lengths`) | 17 | 5 lengths, 52–152 m | yaw 0° / 6° / 12° (102 m also 3° / 9°) |

The freestream speed is constant, so "different inflow" in this data means different yaw
(crosswind) angles. Each 102 m train has about 1.39 × 10⁵ surface cells.

Nose geometries are named `nose_k<k×100>_a<p|m><|a|×100>`: `k` scales the nose length,
`a` sets the profile fullness (`ap25` = +0.25, `am50` = −0.50). Length geometries are
`train_L<length in m>`. Cases append `_yaw<deg>`.

## Format

One PhysicsNeMo `DomainMesh` per case, `<case>/domain.pdmsh`:

| Item | Content |
|---|---|
| `boundaries["vehicle"]` | triangulated surface; cell data `p` [Pa], `wallShearStress` [Pa] |
| `global_data` | `U_inf` [m/s], `rho_inf`, `p_inf`, `nu`, `L_ref` [m], `A_ref` = 11.0888 m², `yaw_deg` |
| `global_data["U_hat"]` | unit freestream direction, added by `train_aero.data.prepare` |

Targets: Cp = (p − p∞) / q∞ (1 channel) and Cf = τ_w / q∞ (3 channels), q∞ = ½ ρ∞ |U∞|².

Each dataset also exists as a `*_shuffled` copy whose cells are stored in random order: the
recipe's mesh reader takes a contiguous block of cells when it subsamples, so training reads the
shuffled copy and evaluation reads the curated order.

## Availability

The full dataset is not redistributed. [`data/sample/`](../data/sample/) contains one case
(`nose_k080_ap00_yaw06`, 13 MB, with `U_hat`) used by the tests; its integrated coefficients
(Cd, Cs, Cl = 0.22341, 0.53385, 0.16958) match the OpenFOAM `forceCoeffs` output.
