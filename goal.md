# Overnight goal — HADR claw

(Read CLAUDE.md and ROADMAP.md first. This file is the standing orders for an
unattended improvement loop; `scripts/overnight.sh` is the harness that runs
it, checks it, and stops it. Distinct from `Goal.md`, the course brief.)

## Target

Improve the claw's **assessment quality against events it has never seen**.
The instructor holds a set of past disaster date-windows; after tonight, the
pipeline and morning engine will be run against those holdout fixtures and
judged on: events found, severities right, duplicates merged, assessments
factual. The holdout set is not in this repository and cannot be enumerated —
optimize the *general* pipeline, not any answer list.

Concrete directions that serve the target (pick what checkers prove weakest):

- Broaden fixture coverage: more hazard types (TC/FL/VO), more revision and
  escalation sequences, malformed-payload cases — with tests.
- Tighten dedup: cross-feed clusters that should merge but don't (or worse,
  do but shouldn't) on the visible fixtures.
- Sharpen assessments: soul.md and briefing changes that make model prose
  more factual and grounded in tool results (never invented).
- Harden feed parsing against real-world payload oddities found in the feeds'
  documentation and fixtures.

## Constraints — each with its checking instrument

| Constraint | Instrument |
|---|---|
| Unified event schema stays valid | `scripts/check_schema.py` |
| Cross-feed dedup stays correct on visible fixtures | `scripts/check_dedup.py` |
| Memory classifies revisions/escalations/deletions correctly | `scripts/check_memory.py` |
| Dashboard facts trace to feed data; nothing unescaped | `scripts/check_dashboard.py` |
| Freshness stamp present and current | `scripts/check_freshness.py` |
| No run exceeds its caps un-tripped | `scripts/check_spend.py` |
| Tests and lint stay green | `uv run pytest` · `uv run ruff check .` |

All of the above must pass after every iteration (`scripts/run_checkers.py`).
The outer loop runs **pristine copies** of the checkers and this file; editing
`scripts/check_*.py`, `run_checkers.py` or `goal.md` voids the iteration.

## Hard caps (enforced by scripts/overnight.sh, not by this prose)

- Wall clock per iteration: 20 minutes (`timeout`).
- Total iterations: 12 by default (`--max-iterations`).
- Total wall clock: 6 hours by default (`--max-minutes`).
- Kill switch: create a file named `.overnight-stop` in the repo root.

## Unattended operation — read this first

You are one iteration of an unattended loop (`scripts/overnight.sh`). **There
is no human at the other end.** A question, a menu of options, or "shall I…?"
is a wasted iteration — nothing will ever answer.

1. Start by reading `git log --oneline -15`: previous iterations' commits show
   what is already done. Do not repeat it.
2. Pick the single highest-value improvement toward the target yourself and
   implement it **fully within this session** — code, tests, docs.
3. Verify before you finish: `uv run pytest`, `uv run ruff check .`,
   `uv run python scripts/run_checkers.py`. Leave the tree green.
4. End your session only after landing a concrete, verified change. Your edits
   are captured by the harness; you do not need to commit or push.

## Rules of engagement

- Work only on the current branch; never push to or merge into `main`.
- No new network dependencies; feeds stay the documented three.
- Documentation stays current every iteration: README, ROADMAP,
  implementation-notes (one entry per iteration), docs/solutions for anything
  that cost more than ten minutes.
- Secrets policy is absolute: no key material in any tracked file.
- If a checker fails and cannot be fixed within the iteration, the harness
  reverts the whole iteration (git reset to the iteration checkpoint).
