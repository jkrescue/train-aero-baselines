"""Map model output points back onto the ground-truth cells by position."""
from __future__ import annotations

import torch

MATCH_TOL_M = 1e-3


def match(pred_pts_m: torch.Tensor, truth_c: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """Index into the truth cells for every predicted point, and the distance to it.

    Predicted points are cell centroids in metres.  When both arrays have the same order
    (the usual case) this is verified rather than assumed; otherwise a float64 KD-tree
    nearest-neighbour query is used.
    """
    if pred_pts_m.shape == truth_c.shape:
        d = (pred_pts_m - truth_c).norm(dim=-1)
        if float(d.max()) < MATCH_TOL_M:
            return torch.arange(truth_c.shape[0]), d
    from scipy.spatial import cKDTree

    dist, idx = cKDTree(truth_c.numpy()).query(pred_pts_m.numpy(), k=1)
    return torch.from_numpy(idx).long(), torch.from_numpy(dist)


def is_one_to_one(idx: torch.Tensor, dist: torch.Tensor, n_truth: int, tol: float = MATCH_TOL_M) -> bool:
    return idx.numel() == n_truth and idx.unique().numel() == n_truth and float(dist.max()) <= tol


def to_truth_order(x: torch.Tensor, idx: torch.Tensor, n: int) -> torch.Tensor:
    out = torch.empty((n, *x.shape[1:]), dtype=torch.float64)
    out[idx] = x.detach().double().cpu()
    return out
