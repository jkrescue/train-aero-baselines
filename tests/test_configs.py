from pathlib import Path

import yaml

from train_aero.benchmark.configs import benchmark_config, infer_overrides, run_label
from train_aero.data.make_folds import RECIPE_CONFIGS, dataset_configs
from train_aero.folds import fold_summary

META = {"fold": "n2", "family": "noses", "model": "abupt", "seed": 0, "tag": "centered", "overrides": "DS=psc"}


def test_committed_dataset_configs_are_reproducible():
    for fold, s in fold_summary().items():
        for name, text in dataset_configs(fold, s["wss_std"]).items():
            assert (RECIPE_CONFIGS / "datasets" / name).read_text() == text, name


def test_centred_point_sets_only_add_center_mesh():
    cfg = dataset_configs("n2", 8e-4)
    ps = yaml.safe_load(cfg["ev_n2_orig_ps.yaml"])
    psc = yaml.safe_load(cfg["ev_n2_orig_psc.yaml"])
    assert psc["pipeline"]["transforms"][0]["_target_"] == "${dp:CenterMesh}"
    assert psc["pipeline"]["transforms"][1:] == ps["pipeline"]["transforms"]
    assert {k: v for k, v in psc.items() if k != "pipeline"} == {k: v for k, v in ps.items() if k != "pipeline"}


def test_infer_overrides_follow_run_one():
    ov = infer_overrides(META, Path("/w/run"))
    assert "model=ev_ab_upt" in ov and "dataset=ev_n2_orig_psc" in ov
    assert "measure_weighted=false" in ov and "sampling_resolution=10000000" in ov
    lr = dict(META, model="gt", tag="lr1e-3", overrides="training.optimizer.lr=1.0e-3 RES=16000 MW=true")
    ov = infer_overrides(lr, Path("/w/run"))
    assert "dataset=ev_n2_orig" in ov and "measure_weighted=true" in ov
    assert not any(o.startswith("training.optimizer") or o.startswith("RES=") for o in ov)
    assert run_label(lr) == "GeoTransolver/seed0__lr1e-3"


def test_benchmark_config_layout():
    cfg = benchmark_config("n2", [], ["nose_k080_ap00_yaw00", "nose_k080_ap00_yaw12"], Path("/r"), Path("/t"))
    assert cfg["benchmark"]["datasets"][0] == {"name": "train_aero", "label": "n2", "root": "/t",
                                               "kwargs": {"fold": "n2"}}
    assert cfg["reports"]["visual_case_ids"] == ["nose_k080_ap00_yaw12"]
    assert {"name": "side_force", "coeff": 1 / 11.0888} in cfg["metrics"]
