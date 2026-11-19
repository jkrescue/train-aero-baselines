# Reproducing the study

## 1. Environment

| Component | Version used |
|---|---|
| Python / PyTorch | 3.12 / 2.14.0+cu130 |
| PhysicsNeMo | source checkout at `fb5b9a2` (provides the unified external-aero recipe) |
| PhysicsNeMo-CFD | source checkout at `43e531a` (provides `workflows/benchmarking`) |
| GPU | RTX PRO 5000 72 GB (training needs up to 22 GB per run) |

```bash
git clone https://github.com/NVIDIA/physicsnemo.git && git -C physicsnemo checkout fb5b9a2
git clone https://github.com/NVIDIA/physicsnemo-cfd.git && git -C physicsnemo-cfd checkout 43e531a
pip install -e physicsnemo -e physicsnemo-cfd      # plus the recipe's requirements.txt
pip install -e ".[dev]"                             # this repository
cp .env.example .env                                # then edit the paths
```

All commands below run from the repository root. Shell scripts read `.env` themselves; for
`python -m ...` export it first (`set -a; . ./.env; set +a`).

## 2. Data and configs

```bash
python -m train_aero.data.prepare       # copy curated cases to $TRAIN_AERO_WORKDIR/data/base, add U_hat
python -m train_aero.data.make_folds    # fold links + manifests + wss std, configs, install into the recipe
```

`make_folds` regenerates `configs/folds.json` and `configs/recipe/` (the committed copies are
the ones used in the study) and copies them into the recipe as new `ev_*` files. To only
install the committed configs: `python -m train_aero.data.make_folds --install`.

Optional checks before training:

```bash
python -m train_aero.runs.inspect_inputs n2      # what each model receives; target stats must agree
scripts/gate_regression.sh v2 0                  # must reproduce the earlier GeoTransolver result
scripts/run_baselines.sh                         # no-learning baselines per fold
```

## 3. Training

```bash
scripts/run_one.sh 0 n2 gt 0 -                   # one run: <gpu> <fold> <model> <seed> <tag|->
python -m train_aero.runs.scheduler              # the whole queue in configs/jobs.txt
```

`configs/jobs.txt` is the job list of the study (one line per run, file order = priority).
Each run writes `$TRAIN_AERO_WORKDIR/runs/<family>/<model>/<fold>/<run>/` with the final
`.mdlus` checkpoint, `metrics.jsonl`, the resolved config, the official `infer.py` predictions
and `run.json` (commit, overrides, time, peak memory).

## 4. Evaluation (PhysicsNeMo-CFD benchmark)

```bash
scripts/run_benchmark.sh 0            # all folds on GPU 0, then the summary
scripts/run_benchmark.sh 0 n2 l1      # selected folds
```

This generates one benchmark config per fold (`bench/conf/train_aero_<fold>.yaml`, same layout
as the official `config_matrix_surface_custom.yaml`), runs the official
`workflows/benchmarking/main.py` with the plugin registered, and writes
`bench/results/<fold>/benchmark_results.{json,csv,html}`, `visuals/` and
`bench/results/BENCH_SUMMARY.md`.

Independent cross-check of the recipe's own predictions (must equal `l2_pressure`):

```bash
python -m train_aero.runs.score
```

## 5. Publishing

```bash
python -m train_aero.release.export --repo . --checkpoints release_assets/
gh release upload <tag> release_assets/*.mdlus
```

`export` copies summaries, per-fold results, figures, baselines and per-run metadata into
`results/`, rewrites absolute paths to `${TRAIN_AERO_WORKDIR}` etc., and writes
`results/checkpoints.json`.

## Platform notes

- WSL2: set `LD_LIBRARY_PATH=/usr/lib/wsl/lib`, otherwise Warp does not see the GPU.
- WSL2 terminates background processes started from an SSH session when it ends; launch long
  queues from the Windows side or keep the session open.
- Two jobs on one GPU gave no throughput gain; the scheduler runs one job per GPU.
