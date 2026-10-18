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
# Scope: inside a git work tree only files git knows about are scanned (tracked files plus new,
# untracked files that are NOT git-ignored: `git ls-files --cached --others --exclude-standard`),
# so git-ignored scratch such as example runs (.odb/.cae/.sat written by Abaqus) never trips the
# gate. Outside a git work tree (for example an unpacked zip) every file is scanned.
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
# ---- file list: git-known files inside a work tree, else everything except .git
LIST="$(mktemp)"
trap 'rm -f "$PATTERNS" "$LIST"' EXIT
if git -C "$REPO" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  SCOPE="git-known files (tracked + untracked, not ignored)"
  (cd "$REPO" && git ls-files -z --cached --others --exclude-standard) |
    while IFS= read -r -d '' f; do [ -f "$REPO/$f" ] && printf '%s\0' "$REPO/$f"; done > "$LIST"
else
  SCOPE="all files (not a git work tree)"
  find "$REPO" -path "$REPO/.git" -prune -o -type f -print0 > "$LIST"
fi
NFILES=$(tr -cd '\0' < "$LIST" | wc -c)
scan() { xargs -0 -r grep "$@" < "$LIST"; }
if [ "$SKIP_DENY" = "1" ]; then
  echo "scrub_check: regex checks only, scanning $NFILES $SCOPE in $REPO"
else
  echo "scrub_check: $N denylist terms, scanning $NFILES $SCOPE in $REPO"
  if out=$(scan -nHiIF -f "$PATTERNS") && [ -n "$out" ]; then
    echo "--- denylisted terms:"; echo "$out"; hits=1
  fi
fi
# every address is checked on its own (-o), so an allowed address cannot hide another one on the same line
if out=$(scan -nHoIE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' |
         awk -v ok="$ALLOWED_EMAILS" '{ a = $0; sub(/^.*:[0-9]+:/, "", a); if (tolower(a) !~ ok) print }') && [ -n "$out" ]; then
  echo "--- e-mail addresses:"; echo "$out"; hits=1
fi
if out=$(scan -nHIE '(^|[^A-Za-z])[A-Za-z]:(\\\\|\\|/)(Users|Documents|Desktop|Temp|SIMULIA|Program)') && [ -n "$out" ]; then
  echo "--- Windows paths:"; echo "$out"; hits=1
fi
if out=$(scan -nHIiE '(^|[^A-Za-z])[A-Za-z]:\\\\?[A-Za-z0-9_ ]+\\') && [ -n "$out" ]; then
  echo "--- Windows paths (generic):"; echo "$out"; hits=1
fi
# binary or result files that should never be committed (checked on the same file list)
out=$(tr '\0' '\n' < "$LIST" | grep -iE '\.(odb|cae|jnl|zip|step|stp|sat|xlsx|pdf)$')
if [ -n "$out" ]; then echo "--- files that must not be in the repo:"; echo "$out"; hits=1; fi
if [ $hits -eq 0 ]; then
  echo "scrub_check: CLEAN"
  exit 0
fi
echo "scrub_check: FAILED"
exit 1
