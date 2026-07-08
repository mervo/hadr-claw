#!/usr/bin/env bash
# Route B overnight loop (Activity 11): run `claude -p` against goal.md, check
# with PRISTINE checkers, repeat until a hard cap trips. Caps live HERE, in
# code — a cap written in goal.md is a request.
#
# Every iteration starts with a checkpoint commit; a red iteration is reverted
# with `git reset --hard` to that checkpoint. Never `git clean` — an automated
# clean once ate this very script (docs/solutions/2026-07-08-git-clean-ate-the-loop.md).
#
#   bash scripts/overnight.sh [--max-iterations N] [--max-minutes M] [--dry-run]
#
# Kill switch: touch .overnight-stop
set -euo pipefail

MAX_ITERATIONS=12
MAX_MINUTES=360
ITERATION_TIMEOUT_MINUTES=20
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --max-iterations) MAX_ITERATIONS="$2"; shift 2 ;;
    --max-minutes)    MAX_MINUTES="$2"; shift 2 ;;
    --dry-run)        DRY_RUN=1; shift ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$BRANCH" == "main" ]]; then
  echo "refusing to run on main — the overnight loop works on a branch" >&2
  exit 2
fi

# Pristine copies: the agent editing checkers or the goal changes nothing.
PRISTINE="$(mktemp -d)"
trap 'rm -rf "$PRISTINE"' EXIT
cp -r scripts "$PRISTINE/scripts"
cp goal.md "$PRISTINE/goal.md"

START_EPOCH=$(date +%s)
LOG="state/overnight.log"
mkdir -p state .overnight/state
echo "== overnight start $(date -u +%FT%TZ) branch=$BRANCH caps: iter=$MAX_ITERATIONS min=$MAX_MINUTES ==" | tee -a "$LOG"

for ((i = 1; i <= MAX_ITERATIONS; i++)); do
  if [[ -f .overnight-stop ]]; then
    echo "stop file found — halting" | tee -a "$LOG"; break
  fi
  ELAPSED_MIN=$(( ($(date +%s) - START_EPOCH) / 60 ))
  if (( ELAPSED_MIN >= MAX_MINUTES )); then
    echo "wall-clock cap (${MAX_MINUTES}m) tripped — halting" | tee -a "$LOG"; break
  fi

  # Checkpoint: everything (tracked + untracked) is committed before the agent
  # runs, so a red iteration reverts losslessly, including new files.
  git add -A
  git commit -q -m "overnight: iteration $i checkpoint [skip ci]" --allow-empty
  CHECKPOINT="$(git rev-parse HEAD)"

  echo "-- iteration $i/$MAX_ITERATIONS (${ELAPSED_MIN}m elapsed) $(date -u +%TZ)" | tee -a "$LOG"

  if (( DRY_RUN )); then
    echo "[dry-run] would run: timeout ${ITERATION_TIMEOUT_MINUTES}m claude -p <goal.md>" | tee -a "$LOG"
  else
    timeout "${ITERATION_TIMEOUT_MINUTES}m" \
      claude -p "$(cat "$PRISTINE/goal.md")" --permission-mode acceptEdits \
      2>&1 | tail -5 | tee -a "$LOG" || echo "iteration $i: claude exited nonzero/timeout" | tee -a "$LOG"
  fi

  # Anti-cheat gate: the goal and its instruments are read-only for the agent.
  # Compare against the PRISTINE copies (never HEAD — the checkpoint commit
  # happily commits tampering, and the agent can commit on its own too).
  # A tampered iteration is VOID in full: everything it did is discarded, per
  # goal.md's contract — restoring only the protected file would let the rest
  # of a cheating iteration's work survive.
  TAMPERED=""
  if ! diff -q "$PRISTINE/goal.md" goal.md >/dev/null 2>&1; then
    TAMPERED+="goal.md "
  fi
  for f in "$PRISTINE"/scripts/check_*.py "$PRISTINE"/scripts/run_checkers.py "$PRISTINE"/scripts/overnight.sh; do
    rel="scripts/$(basename "$f")"
    if ! diff -q "$f" "$rel" >/dev/null 2>&1; then
      TAMPERED+="$rel "
    fi
  done
  if [[ -n "$TAMPERED" ]]; then
    echo "iteration $i: VOID — protected files modified ($TAMPERED); discarding the whole iteration" | tee -a "$LOG"
    git reset --hard "$CHECKPOINT" >/dev/null
    continue
  fi

  # Fresh outputs for the freshness/dashboard checkers, then PRISTINE checkers.
  uv run python -m hadr --fixtures tests/fixtures \
    --out .overnight/dash.html --state .overnight/state/seen.json >/dev/null 2>&1 || true
  if uv run python "$PRISTINE/scripts/run_checkers.py" \
       --dashboard .overnight/dash.html --state .overnight/state/seen.json \
       >>"$LOG" 2>&1 \
     && uv run pytest -q >>"$LOG" 2>&1 \
     && uv run ruff check . >>"$LOG" 2>&1; then
    echo "iteration $i: checkers green" | tee -a "$LOG"
    # commit the green work now — if a cap trips before the next iteration's
    # checkpoint, nothing green may be left uncommitted
    git add -A
    git commit -q -m "overnight: iteration $i green [skip ci]" --allow-empty
  else
    echo "iteration $i: checkers RED — reverting to checkpoint" | tee -a "$LOG"
    git reset --hard "$CHECKPOINT" >/dev/null
  fi
done

echo "== overnight end $(date -u +%FT%TZ) after $(( ($(date +%s) - START_EPOCH) / 60 ))m ==" | tee -a "$LOG"
