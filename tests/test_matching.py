import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("scipy")

from train_aero.matching import is_one_to_one, match, to_truth_order  # noqa: E402


def test_match_recovers_permutation():
    truth = torch.rand(500, 3, dtype=torch.float64) * 100
    perm = torch.randperm(500)
    idx, dist = match(truth[perm], truth)
    assert torch.equal(idx, perm) and float(dist.max()) == 0.0
    assert is_one_to_one(idx, dist, 500)
    values = torch.arange(500, dtype=torch.float64)[perm]
    assert torch.equal(to_truth_order(values, idx, 500), torch.arange(500, dtype=torch.float64))


def test_match_same_order_is_verified_not_assumed():
    truth = torch.rand(100, 3, dtype=torch.float64)
    idx, _ = match(truth.clone(), truth)
    assert torch.equal(idx, torch.arange(100))
    idx, dist = match(truth + 0.5, truth)          # same shape, wrong positions
    assert not is_one_to_one(idx, dist, 100)
