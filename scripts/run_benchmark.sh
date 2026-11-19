#!/usr/bin/env bash
# PhysicsNeMo-CFD benchmark over every fold with finished runs, then the summary.
#
#   scripts/run_benchmark.sh [gpu] [fold ...]      (default: GPU 0, all folds)
set -uo pipefail
source "$(dirname "$0")/env.sh"
: "${PHYSICSNEMO_CFD_ROOT:?PHYSICSNEMO_CFD_ROOT is not set (see .env.example)}"
export CUDA_VISIBLE_DEVICES=${1:-0}; shift $(( $# > 0 ? 1 : 0 ))
BENCH=$TRAIN_AERO_WORKDIR/bench
mkdir -p "$BENCH/logs"

$PYTHON -m train_aero.benchmark.configs
FOLDS=("$@")
if [ ${#FOLDS[@]} -eq 0 ]; then
  for c in "$BENCH"/conf/train_aero_*.yaml; do f=$(basename "$c" .yaml); FOLDS+=("${f#train_aero_}"); done
fi
for f in "${FOLDS[@]}"; do
  $PYTHON -m train_aero.benchmark.launch --config-path="$BENCH/conf" --config-name="train_aero_$f" \
    > "$BENCH/logs/$f.log" 2>&1
  echo "$f rc=$? $(grep -a 'Completed' "$BENCH/logs/$f.log")"
done
$PYTHON -m train_aero.benchmark.summarize > /dev/null && echo "summary -> $BENCH/results/BENCH_SUMMARY.md"
