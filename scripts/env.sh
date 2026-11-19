# Common environment of the shell entry points.  Sourced, not executed.
# Reads <repo>/.env (see .env.example) and derives the recipe path.
REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
if [ -f "$REPO_ROOT/.env" ]; then set -a; . "$REPO_ROOT/.env"; set +a; fi
: "${PHYSICSNEMO_ROOT:?PHYSICSNEMO_ROOT is not set (see .env.example)}"
export TRAIN_AERO_WORKDIR=${TRAIN_AERO_WORKDIR:-$REPO_ROOT/workdir}
export PYTHONPATH=$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}
RECIPE=$PHYSICSNEMO_ROOT/examples/cfd/external_aerodynamics/unified_external_aero_recipe
PYTHON=${PYTHON:-python}
A_REF=11.0888            # frontal reference area, m^2
FULL_MESH=10000000       # sampling_resolution larger than any mesh: score on every cell

# family, recipe model config and default dataset suffix of <fold> <model>
resolve_run() {
  case $1 in n*) FAM=noses ;; l*) FAM=lengths ;; *) echo "unknown fold $1" >&2; return 1 ;; esac
  case $2 in
    gt)    CFG=ev_geotransolver; SFX="" ;;
    smart) CFG=ev_smart_$FAM;    SFX="" ;;
    abupt) CFG=ev_ab_upt;        SFX="_ps" ;;   # AB-UPT reads point sets
    *) echo "unknown model $2" >&2; return 1 ;;
  esac
}
