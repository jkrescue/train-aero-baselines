#!/usr/bin/env bash
# Regression gate: retrain GeoTransolver on the original nose split (seed 0) in the current
# environment; it must reproduce the earlier result (Cp relative L2 0.1399) before any
# comparison is trusted.
#
#   scripts/gate_regression.sh <name> <gpu> [hydra overrides...]
#
# Datasets `train_noses_shuffled` (train) and `train_noses` (test) must be registered in the
# recipe's datasets/dataset_paths.yaml.
set -uo pipefail
source "$(dirname "$0")/env.sh"
NAME=$1; GPU=$2; shift 2
OUT=$TRAIN_AERO_WORKDIR/gates/$NAME
export CUDA_VISIBLE_DEVICES=$GPU
cd "$RECIPE" || exit 2
rm -rf "$OUT" "${OUT}_infer"
PYTHONPATH=src $PYTHON src/train.py model=geotransolver_surface dataset=train_noses_shuffled \
  sampling_resolution=32000 training.num_epochs=300 training.seed=0 training.save_interval=300 \
  training.scheduler.step_size=150 training.scheduler.gamma=0.1 \
  compile=false precision=float32 run_id=gt output_dir="$OUT" "$@"
PYTHONPATH=src $PYTHON src/infer.py model=geotransolver_surface dataset=train_noses \
  sampling_resolution=$FULL_MESH compile=false precision=float32 \
  run_id=gt checkpoint_dir="$OUT" output_dir="${OUT}_infer" infer_split=test \
  force_coefficients.reference_area=$A_REF "$@"
