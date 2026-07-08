---
date: 2026-07-08
tags: [overnight-loop, claude-cli, usage-limits, route-b]
problem: The overnight loop consumed iterations 2-12 in two minutes with "claude exited nonzero/timeout"
---

# Account usage limits burn loop iterations unless the loop waits

**Symptom:** after a productive iteration 1, every remaining iteration of
`overnight.sh` failed within ~3 seconds; the log shows
`You've hit your session limit · resets 2:10pm (Asia/Singapore)`.

**Cause:** Route B's `claude -p` draws on the same account limits as
interactive sessions (the course brief warned about this for Route A — it
applies equally here). When the window is exhausted, the CLI exits instantly;
the loop counted each instant failure as a spent iteration and torched its
whole budget of 12 in two minutes.

**Fix:** `overnight.sh` now greps the claude output for `session limit` /
`usage limit`; on a hit it resets to the checkpoint, does **not** count the
iteration, and sleeps 15 minutes before retrying. The wall-clock cap still
bounds the whole run, so this cannot loop forever.

**Also fixed here:** `python -m hadr` wrote its run record to the repo's
`state/runs/` even when `--state` pointed at a scratch directory — every
checker regen inside the loop polluted the branch with `state/**` churn
(which dev PRs must not diff). Run records now live next to their state file.

**Rule of thumb:** an unattended loop's failure classifier must distinguish
"the work failed" (count it, move on) from "the world is temporarily closed"
(wait, don't count). Only the first should consume budget.
