#!/usr/bin/env bash
# run_job.sh - build a model from a JSON spec, optionally datacheck it, run it, triage the logs.
#
#   scripts/run_job.sh SPEC.json JOBNAME [--cpus N] [--datacheck] [--double] [--no-run]
#
# Environment:
#   ABAQUS   launcher command (default: abaqus). On Windows from Git Bash this is usually the
#            full path of abaqus.bat in the SIMULIA "Commands" folder, quoted.
#   SCRATCH  scratch directory WITHOUT spaces (default: none). Paths with spaces break some solvers.
#
# Long jobs: this script runs the solver in the foreground ("interactive"). If your agent
# shell has a timeout, launch it detached instead (nohup ... &) and poll the .sta file;
# a killed shell sends SIGTERM to the solver.
#
# OhmFrame - https://ohmframe.com - MIT licence.
set -euo pipefail

SPEC=${1:?spec.json}; JOB=${2:?job name}; shift 2
CPUS=1; DATACHECK=0; DOUBLE=""; RUN=1
while [ $# -gt 0 ]; do
  case "$1" in
    --cpus) CPUS=$2; shift ;;
    --datacheck) DATACHECK=1 ;;
    --double) DOUBLE="double=both" ;;
    --no-run) RUN=0 ;;
    *) echo "unknown option $1"; exit 2 ;;
  esac
  shift
done
ABQ=${ABAQUS:-abaqus}
HERE=$(cd "$(dirname "$0")" && pwd)
RUNDIR=$(cd "$(dirname "$SPEC")" && pwd)
SCR=${SCRATCH:+scratch=$SCRATCH}

echo "== build: $ABQ cae noGUI=build_from_spec.py -- $(basename "$SPEC")"
( cd "$RUNDIR" && $ABQ cae noGUI="$HERE/build_from_spec.py" -- "$(basename "$SPEC")" )

cd "$RUNDIR"
if [ "$DATACHECK" = 1 ]; then
  echo "== datacheck"
  $ABQ job="${JOB}_check" input="$JOB.inp" datacheck $DOUBLE $SCR ask_delete=OFF interactive || true
  python "$HERE/check_logs.py" "${JOB}_check" || true
fi
if [ "$RUN" = 1 ]; then
  echo "== run"
  $ABQ job="$JOB" input="$JOB.inp" cpus="$CPUS" $DOUBLE $SCR ask_delete=OFF interactive || true
  python "$HERE/check_logs.py" "$JOB" --json "${JOB}_logcheck.json"
fi
