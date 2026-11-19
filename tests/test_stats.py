import math

import pytest

from train_aero.stats import error_over_span, paired_difference


def _row(case_id, true, pred):
    return {"case_id": case_id, "metrics": {"side_force_true": true, "side_force_pred": pred}}


def test_error_over_span_uses_truth_span_per_geometry():
    rows = [_row("g1_yaw00", 0.0, 0.01), _row("g1_yaw06", 0.25, 0.24), _row("g1_yaw12", 0.5, 0.52),
            _row("g2_yaw00", 0.0, 0.0), _row("g2_yaw12", 1.0, 0.9)]
    err, sign = error_over_span(rows, "side_force")
    expected = [0.01 / 0.5, 0.01 / 0.5, 0.02 / 0.5, 0.0, 0.1]
    assert err == pytest.approx(sum(expected) / len(expected))
    # yaw-0 cases (|truth| <= 10 % of span) are excluded from the sign count
    assert sign == 1.0


def test_error_over_span_counts_wrong_sign():
    rows = [_row("g_yaw00", 0.0, 0.0), _row("g_yaw12", 1.0, -0.2)]
    _, sign = error_over_span(rows, "side_force")
    assert sign == 0.0


def test_paired_difference():
    d = paired_difference([0.2, 0.3, 0.4], [0.1, 0.1, 0.1])
    assert d["n"] == 3 and d["a_worse"] == 3
    assert d["mean"] == pytest.approx(0.2)
    assert d["t"] == pytest.approx(0.2 / (0.1 / math.sqrt(3)))
    with pytest.raises(ValueError):
        paired_difference([0.1], [0.2])
