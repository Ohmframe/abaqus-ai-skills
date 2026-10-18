#!/usr/bin/env bash
# compile_check.sh - every .py must byte-compile, and pass the Python 2.7/3 + Abaqus hazard linter.
#   scripts/compile_check.sh
# Uses python3 (and python2 too, if installed). Exit 0 = all good.
# Python 2.7 is optional: GitHub's ubuntu-latest runners ship no python2, so in CI the 2.7
# byte-compile is skipped (reported as 'skipped') and only python3 + the py23 linter run. The
# linter (py23_check.py) still flags Python-2.7 hazards such as f-strings. To cover 2.7 locally,
# put a python2 interpreter on PATH before running this script.
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
rc=0
TMPC="$(mktemp)"; TMPE="$(mktemp)"
trap 'rm -f "$TMPC" "$TMPE"' EXIT
mapfile -t FILES < <(find "$REPO" -path "$REPO/.git" -prune -o -name '*.py' -print | sort)
for py in python3 python2; do
  command -v "$py" >/dev/null 2>&1 || { echo "compile_check: $py not installed - skipped"; continue; }
  bad=0
  for f in "${FILES[@]}"; do
    if ! "$py" -c "import py_compile,sys; py_compile.compile(sys.argv[1], cfile=sys.argv[2], doraise=True)" "$f" "$TMPC" 2>"$TMPE"; then
      echo "FAIL ($py): $f"; cat "$TMPE"; bad=1; rc=1
    fi
  done
  [ $bad -eq 0 ] && echo "compile_check: $py py_compile OK (${#FILES[@]} files)"
done
find "$REPO" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null
find "$REPO" -name '*.pyc' -delete 2>/dev/null
python3 "$REPO/skills/abaqus-version-compat/scripts/py23_check.py" "$REPO/skills" || rc=1
for s in "$REPO"/scripts/*.sh "$REPO"/skills/*/scripts/*.sh; do
  [ -f "$s" ] || continue
  bash -n "$s" || { echo "FAIL bash -n: $s"; rc=1; }
done
exit $rc
