#!/usr/bin/env bash
# Re-run only the official inference of a finished training run (same call as run_one.sh).
#
#   scripts/infer_only.sh <gpu> <fold> <gt|smart|abupt> <seed> <tag|-> [MW=<bool>] [DS=<suffix>]
set -uo pipefail
source "$(dirname "$0")/env.sh"
GPU=$1; FOLD=$2; MODEL=$3; SEED=$4; TAG=$5; shift 5
resolve_run "$FOLD" "$MODEL" || exit 2
NAME=seed$SEED; [ "$TAG" != "-" ] && NAME=${NAME}__$TAG
RUN=$TRAIN_AERO_WORKDIR/runs/$FAM/$MODEL/$FOLD/$NAME
MW=false; for a in "$@"; do case $a in MW=*) MW=${a#MW=} ;; DS=*) SFX=_${a#DS=} ;; esac; done

export CUDA_VISIBLE_DEVICES=$GPU
cd "$RECIPE" || exit 2
rm -rf "$RUN/infer"
PYTHONPATH=src $PYTHON src/infer.py model=$CFG compile=false precision=float32 run_id=train measure_weighted=$MW \
  dataset=ev_${FOLD}_orig$SFX sampling_resolution=$FULL_MESH \
  checkpoint_dir="$RUN" output_dir="$RUN/infer" infer_split=test \
  force_coefficients.reference_area=$A_REF > "$RUN/infer.log" 2>&1
RC=$?
sed -i "s/\"infer_rc\": [0-9]*/\"infer_rc\": $RC/" "$RUN/run.json"
echo "infer rc=$RC $RUN"
