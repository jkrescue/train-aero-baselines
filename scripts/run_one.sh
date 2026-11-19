#!/usr/bin/env bash
# One training + inference run through the official recipe entry points.
#
#   scripts/run_one.sh <gpu> <fold> <gt|smart|abupt> <seed> <tag|-> [OPTION=value | hydra overrides]
#
# Options: RES=<points>  supervised points per step (default 32000)
#          MW=<bool>     measure_weighted loss (default false)
#          DS=<suffix>   dataset suffix, e.g. DS=psc for the centred AB-UPT diagnostic
# Output:  $TRAIN_AERO_WORKDIR/runs/<family>/<model>/<fold>/seed<k>[__<tag>]/
#          {train/, infer/, run.json, train.log, infer.log}
set -uo pipefail
source "$(dirname "$0")/env.sh"
GPU=$1; FOLD=$2; MODEL=$3; SEED=$4; TAG=$5; shift 5
resolve_run "$FOLD" "$MODEL" || exit 2

NAME=seed$SEED; [ "$TAG" != "-" ] && NAME=${NAME}__$TAG
RUN=$TRAIN_AERO_WORKDIR/runs/$FAM/$MODEL/$FOLD/$NAME
mkdir -p "$RUN"
if grep -q infer_summary "$RUN/infer/train/metrics.jsonl" 2>/dev/null; then echo "skip $RUN"; exit 0; fi

RES=32000; MW=false; EXTRA=()
for a in "$@"; do
  case $a in RES=*) RES=${a#RES=} ;; MW=*) MW=${a#MW=} ;; DS=*) SFX=_${a#DS=} ;; *) EXTRA+=("$a") ;; esac
done
# measure_weighted: upstream d919d80 made area weighting the default; the study uses the
# per-cell loss (the validated setting and the primary metric) for all three models.
COMMON=(model=$CFG compile=false precision=float32 run_id=train measure_weighted=$MW "${EXTRA[@]}")
# training.* overrides (LR sweep) are rejected by the inference config
ICOMMON=(); for a in "${COMMON[@]}"; do case $a in training.*) ;; *) ICOMMON+=("$a") ;; esac; done

export CUDA_VISIBLE_DEVICES=$GPU
cd "$RECIPE" || exit 2
rm -rf "$RUN/train" "$RUN/infer"
T0=$(date +%s)
PYTHONPATH=src $PYTHON src/train.py "${COMMON[@]}" dataset=ev_${FOLD}_shuf$SFX sampling_resolution=$RES \
  training.num_epochs=300 training.seed=$SEED training.save_interval=100 \
  training.scheduler.step_size=150 training.scheduler.gamma=0.1 \
  output_dir="$RUN" > "$RUN/train.log" 2>&1
RC1=$?; T1=$(date +%s)
PYTHONPATH=src $PYTHON src/infer.py "${ICOMMON[@]}" dataset=ev_${FOLD}_orig$SFX sampling_resolution=$FULL_MESH \
  checkpoint_dir="$RUN" output_dir="$RUN/infer" infer_split=test \
  force_coefficients.reference_area=$A_REF > "$RUN/infer.log" 2>&1
RC2=$?; T2=$(date +%s)

PEAK=$(grep -o "Mem: [0-9.]*GB" "$RUN/train.log" | sort -t' ' -k2 -n | tail -1)
# keep only the final checkpoint
CK=$RUN/train/checkpoints
[ -d "$CK" ] && find "$CK" -maxdepth 1 -type f ! -regex '.*\.0\.300\.\(mdlus\|pt\)$' -delete
cat > "$RUN/run.json" <<J
{"fold": "$FOLD", "family": "$FAM", "model": "$MODEL", "config": "$CFG", "seed": $SEED, "tag": "$TAG",
 "overrides": "$*", "gpu": $GPU, "physicsnemo_commit": "$(git -C "$PHYSICSNEMO_ROOT" rev-parse --short HEAD)",
 "train_rc": $RC1, "infer_rc": $RC2, "train_seconds": $((T1-T0)), "infer_seconds": $((T2-T1)), "peak_train_mem": "$PEAK",
 "finished": "$(date -Is)"}
J
echo "done $RUN rc=$RC1/$RC2 train=$((T1-T0))s"
