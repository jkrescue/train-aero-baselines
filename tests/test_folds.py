from collections import Counter

from train_aero.folds import (
    FOLDS,
    LENGTH_GEOMETRIES,
    NOSE_GEOMETRIES,
    fold_summary,
    geometry_of,
    recipe_model_config,
    validation_case,
)


def test_every_nose_geometry_is_tested_exactly_once():
    tested = Counter(g for spec in FOLDS.values() if spec["family"] == "noses" for g in spec["test"])
    assert set(tested) == set(NOSE_GEOMETRIES)
    assert set(tested.values()) == {1}


def test_length_folds_hold_out_known_geometries():
    for spec in FOLDS.values():
        if spec["family"] == "lengths":
            assert set(spec["test"]) <= set(LENGTH_GEOMETRIES)


def test_validation_case_is_not_a_test_geometry():
    for fold, spec in FOLDS.items():
        assert geometry_of(validation_case(fold)) not in spec["test"]


def test_folds_json_matches_definition():
    summary = fold_summary()
    assert set(summary) == set(FOLDS)
    for fold, spec in FOLDS.items():
        assert summary[fold]["family"] == spec["family"]
        assert summary[fold]["test_geometries"] == spec["test"]
        assert summary[fold]["n_test"] == 3 * len(spec["test"])


def test_recipe_model_config_names():
    assert recipe_model_config("gt", "noses") == "ev_geotransolver"
    assert recipe_model_config("smart", "lengths") == "ev_smart_lengths"
    assert recipe_model_config("abupt", "noses") == "ev_ab_upt"
