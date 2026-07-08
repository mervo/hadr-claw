---
date: 2026-07-08
tags: [git, automation, overnight-loop, data-loss]
problem: The overnight loop's revert path deleted its own goal file and checker scripts
---

# Never `git clean` in an automated revert path

**Symptom:** after the first red iteration of `overnight.sh --dry-run`, the
second iteration silently did nothing; `goal.md`, `overnight.sh` and the new
checkers had vanished from the working tree.

**Cause:** the red path ran `git checkout -- . && git clean -fd`. The files
being developed in that same session were still **untracked**, so "remove
untracked files" removed the loop's own goal, harness and instruments. A
second bug compounded it: pristine checker copies did
`sys.path.insert(Path(__file__).parent.parent)`, which points at the temp
dir when the copy runs — `ModuleNotFoundError: hadr` made every iteration
red, so the destructive path always fired.

**Fix:**
- Revert by **checkpoint commit**: `git add -A && git commit` before the agent
  runs; red iteration → `git reset --hard <checkpoint>`. Lossless for tracked
  and new files alike; the checkpoints double as an audit trail on the branch.
- `run_checkers.py` passes `PYTHONPATH=$PWD` to child checkers so copies run
  from anywhere; checkers prefer `Path.cwd()` over `__file__`-relative roots.

**Rule of thumb:** an unattended loop may only revert through mechanisms that
are themselves reversible. `git reset --hard <known commit>` qualifies;
`git clean` does not.
