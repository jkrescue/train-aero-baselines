#!/usr/bin/env bash
# No-learning control baselines on every fold's held-out geometries.
#
#   scripts/run_baselines.sh [fold ...]           (default: all folds)
set -uo pipefail
source "$(dirname "$0")/env.sh"
OUT=$TRAIN_AERO_WORKDIR/results/baselines
mkdir -p "$OUT"
FOLDS=("$@"); [ ${#FOLDS[@]} -eq 0 ] && FOLDS=(n1 n2 n3 n4 n5 l1 l2 l3)
for f in "${FOLDS[@]}"; do
  case $f in n*) M=nose ;; l*) M=length ;; esac
  $PYTHON -m train_aero.baselines.$M --dataset "$TRAIN_AERO_WORKDIR/data/${f}_orig" --out "$OUT/$f.json" \
    > "$OUT/$f.log" 2>&1
  echo "$f rc=$?"
done
