#!/usr/bin/env bash
# scrub_check.sh - confidentiality gate. Fails if any file in the repo contains a denylisted term,
# an e-mail address or a Windows user/drive path.
#
#   scripts/scrub_check.sh [DENYLIST_FILE]
#   scripts/scrub_check.sh --no-denylist          # regex checks only (CI mode)
#   SCRUB_SKIP_DENYLIST=1 scripts/scrub_check.sh  # same as --no-denylist
#
# The denylist lives OUTSIDE the repository on purpose (the list itself is confidential):
# one fixed string per line, case-insensitive, '#' starts a comment. Default location:
# $SCRUB_DENYLIST, else ../denylist.txt next to the repository folder.
#
# CI mode: the denylist step is skipped when --no-denylist or SCRUB_SKIP_DENYLIST=1 is given, or
# when the denylist is missing AND the script runs in CI (CI=true, set by GitHub Actions).
# Everywhere else a missing denylist is still an error, so a local run cannot silently skip it.
# The e-mail, path and file checks always run.
#
# Allowed e-mail addresses: the generic OhmFrame role addresses below (used in CODE_OF_CONDUCT.md,
# SECURITY.md and the issue templates). Any other address fails the check.
#
# Exit 0 = clean, 1 = hits found, 2 = usage/denylist problem.
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ALLOWED_EMAILS='^(conduct|security|noreply)@ohmframe\.com$'
SKIP_DENY="${SCRUB_SKIP_DENYLIST:-0}"
if [ "${1:-}" = "--no-denylist" ]; then
  SKIP_DENY=1
  shift
fi
DENY="${1:-${SCRUB_DENYLIST:-$REPO/../denylist.txt}}"
if [ "$SKIP_DENY" != "1" ] && [ ! -f "$DENY" ] && [ "${CI:-}" = "true" ]; then
  echo "scrub_check: CI=true and no denylist at $DENY - running in CI mode"
  SKIP_DENY=1
fi
PATTERNS="$(mktemp)"
trap 'rm -f "$PATTERNS"' EXIT
if [ "$SKIP_DENY" = "1" ]; then
  echo "scrub_check: denylist step SKIPPED (CI mode); regex and file checks still run"
else
  if [ ! -f "$DENY" ]; then
    echo "scrub_check: denylist not found: $DENY" >&2
    echo "scrub_check: pass a denylist, or use --no-denylist / SCRUB_SKIP_DENYLIST=1 for regex checks only" >&2
    exit 2
  fi
  case "$(cd "$(dirname "$DENY")" && pwd)/" in
    "$REPO"/*) echo "scrub_check: the denylist must not live inside the repository" >&2; exit 2 ;;
  esac
  sed -e 's/[[:space:]]*#.*$//' -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' "$DENY" | grep -v '^$' > "$PATTERNS"
  N=$(wc -l < "$PATTERNS")
  if [ "$N" -eq 0 ]; then
    echo "scrub_check: denylist is empty" >&2
    exit 2
  fi
fi
hits=0
if [ "$SKIP_DENY" = "1" ]; then
  echo "scrub_check: regex checks only, scanning $REPO"
else
  echo "scrub_check: $N denylist terms, scanning $REPO"
  if out=$(grep -rniIF --exclude-dir=.git -f "$PATTERNS" "$REPO"); then
    echo "--- denylisted terms:"; echo "$out"; hits=1
  fi
fi
# every address is checked on its own (-o), so an allowed address cannot hide another one on the same line
if out=$(grep -rnoIE --exclude-dir=.git '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' "$REPO" |
         awk -v ok="$ALLOWED_EMAILS" '{ a = $0; sub(/^.*:[0-9]+:/, "", a); if (tolower(a) !~ ok) print }') && [ -n "$out" ]; then
  echo "--- e-mail addresses:"; echo "$out"; hits=1
fi
if out=$(grep -rnIE --exclude-dir=.git '(^|[^A-Za-z])[A-Za-z]:(\\\\|\\|/)(Users|Documents|Desktop|Temp|SIMULIA|Program)' "$REPO"); then
  echo "--- Windows paths:"; echo "$out"; hits=1
fi
if out=$(grep -rnIiE --exclude-dir=.git '(^|[^A-Za-z])[A-Za-z]:\\\\?[A-Za-z0-9_ ]+\\' "$REPO"); then
  echo "--- Windows paths (generic):"; echo "$out"; hits=1
fi
# binary or result files that should never be committed
if out=$(find "$REPO" -path "$REPO/.git" -prune -o -type f \( -iname '*.odb' -o -iname '*.cae' -o -iname '*.jnl' \
         -o -iname '*.zip' -o -iname '*.step' -o -iname '*.stp' -o -iname '*.sat' -o -iname '*.xlsx' -o -iname '*.pdf' \) -print); then
  if [ -n "$out" ]; then echo "--- files that must not be in the repo:"; echo "$out"; hits=1; fi
fi
if [ $hits -eq 0 ]; then
  echo "scrub_check: CLEAN"
  exit 0
fi
echo "scrub_check: FAILED"
exit 1
