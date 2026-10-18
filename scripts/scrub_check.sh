#!/usr/bin/env bash
# scrub_check.sh - confidentiality gate. Fails if any file in the repo contains a denylisted term,
# an e-mail address or a Windows user/drive path.
#
#   scripts/scrub_check.sh [DENYLIST_FILE]
#
# The denylist lives OUTSIDE the repository on purpose (the list itself is confidential):
# one fixed string per line, case-insensitive, '#' starts a comment. Default location:
# $SCRUB_DENYLIST, else ../denylist.txt next to the repository folder.
# Exit 0 = clean, 1 = hits found, 2 = usage/denylist problem.
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DENY="${1:-${SCRUB_DENYLIST:-$REPO/../denylist.txt}}"
if [ ! -f "$DENY" ]; then
  echo "scrub_check: denylist not found: $DENY" >&2
  exit 2
fi
case "$(cd "$(dirname "$DENY")" && pwd)/" in
  "$REPO"/*) echo "scrub_check: the denylist must not live inside the repository" >&2; exit 2 ;;
esac
PATTERNS="$(mktemp)"
trap 'rm -f "$PATTERNS"' EXIT
sed -e 's/[[:space:]]*#.*$//' -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' "$DENY" | grep -v '^$' > "$PATTERNS"
N=$(wc -l < "$PATTERNS")
if [ "$N" -eq 0 ]; then
  echo "scrub_check: denylist is empty" >&2
  exit 2
fi
hits=0
echo "scrub_check: $N denylist terms, scanning $REPO"
if out=$(grep -rniIF --exclude-dir=.git -f "$PATTERNS" "$REPO"); then
  echo "--- denylisted terms:"; echo "$out"; hits=1
fi
if out=$(grep -rnIE --exclude-dir=.git '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' "$REPO"); then
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
