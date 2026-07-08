# Implementation notes

Kept by the agent, reviewed by you. One entry per working block.

## Decisions

### 2026-07-08 — Tier 0: plan + docs foundation

Progressive plan agreed with user (full plan archived in this session; tier table
and decisions of record in ROADMAP.md). Headlines:

- Agentic harness (Activity 7 loop) is the production engine; deterministic
  pipeline in `hadr/` is the seatbelt (caps in code, structured tool args,
  fallback renderer — the morning report can never fail to exist).
- Model API: OpenCode Go (Zen gateway, OpenAI-compatible, env-configured).
- Runtime: docker-compose canonical; uv for the dev loop.
- Heartbeat: GitHub Actions cron 00:00 UTC + workflow_dispatch; VPS-portable
  supercronic compose profile as documented alternative.
- Observability: run records + transcripts in state/runs/, ops panel on the
  dashboard, OTel traces with jaeger compose profile.
- Alerting: @claude GitHub issue via PAT + Telegram/Slack webhook.
- Audience: global watch floor. ReliefWeb via RSS until appname approved.
- OPENCODE_API_KEY: `.env` locally + GitHub Actions secret; value in no tracked file.

### 2026-07-08 — Tier 1: slice one (USGS → dashboard)

- `pyproject.toml` has no build-system on purpose (uv "virtual" project — nothing
  to package); tests import via `pythonpath = ["."]`.
- `.python-version` pins 3.12 so local uv matches the `python:3.12-slim` image
  (uv otherwise grabbed its newest managed CPython, 3.14).
- Container venv lives at `/opt/venv` (`UV_PROJECT_ENVIRONMENT`) so bind-mounting
  the working copy over `/app` doesn't shadow it.
- Noise filter (CLAUDE.md): mag≥4.5 OR sig≥600 OR PAGER alert non-null. Live feed
  today: 245 raw → 17 significant.
- Observed a transient DNS failure on the first live run — the per-feed isolation
  path handled it (banner + run record, exit 0), which is the designed behaviour.
- USGS fixture: 17 significant + 10 below-threshold + 1 non-earthquake, trimmed
  from a live capture so tests exercise the filter both ways.

### 2026-07-08 — Tier 2: all feeds + dedup

- GDACS naive datetimes verified UTC empirically: 18/19 live GDACS quakes
  matched USGS records within 100 km/30 min at sub-second time offsets.
- GDACS `sourceid` is empty in the live event list — the NEIC id is NOT
  exposed there, so the alias rule rarely fires; spatio-temporal matching is
  the workhorse (live: 59 raw records → 41 events, 18 merged away).
- GLIDE present on only ~3/100 GDACS events — but exactly the Orange/Red ones,
  and it's what ties ReliefWeb in days later.
- ReliefWeb entries have no coordinates → `Event.lat/lon` became `float | None`.
- GDACS noise filter: Orange/Red always; Green only EQ with mag ≥ 4.5 (76 of
  100 live events were Green wildfires — dropped).
- Feed answers recorded in feeds/gdacs.md and feeds/reliefweb.md.

### 2026-07-08 — Tier 3: memory & change detection

- State matches events by uid, then by any shared source id: a cluster's
  canonical uid changes when a GLIDE arrives late, and alias matching keeps
  that from reading as a deletion plus a new event.
- Fingerprints round lat/lon to 2 dp and mag to 1 dp; `sig`/`felt`/`updated_at`
  excluded — they churn on every USGS revision cycle.
- DELETED requires *inside the feed's rolling window*; only USGS has one
  (24 h). GDACS/ReliefWeb disappearances always age out silently.
- Quiet = content, not absence: the dashboard is rewritten every run (stamp
  advances), leading with "No new developments since <last change>".
- Live verification: run 1 → 41 new; run 2 → "no changes", quiet lead renders.

### 2026-07-08 — Tier 4: the 5-level harness

- Built as five commits, each a runnable checkpoint (chat loop → soul →
  fetch_feed → agent loop → write_dashboard); final harness is ~80 lines.
- Zen gateway verified with curl before building: 51 models listed;
  paid models (kimi-k2.7-code) blocked by CreditsError until balance topped
  up (**user action**); `deepseek-v4-flash-free` does clean tool calls with
  usage populated → dev/CI default. Details in docs/solutions/.
- First live full flight: the model's first two write_dashboard calls were
  rejected by uid validation and it self-corrected from the error feedback —
  the guardrail works, and the recorded transcript
  (tests/fixtures/transcripts/report.json) replays that exact exchange in CI.
- Transcripts embed a tool-schema hash; replay against changed schemas fails
  loudly instead of passing a stale test.

### 2026-07-08 — Tier 5: production engine + observability

- First live morning run fell back with cap_tripped=tokens: the model ignored
  "already fetched" and re-fetched all three feeds (135k chars of context),
  and `max_tokens=2048` truncated its long write_dashboard JSON mid-string.
  Fixes: completion budget 8192, briefing explicitly forbids fetch_feed,
  two-sentence cap per assessment. After: 1 turn, ~7k tokens, engine=agentic
  (22x cheaper). Lesson recorded in docs/solutions/.
- check_spend semantics: a tripped cap that stopped the run is enforcement
  *working*; the failure mode is overspend with no trip recorded.
- Quiet mornings short-circuit to the deterministic renderer without a model
  call (proven by a test that hands the quiet path a broken model).
- Spans: OTLP when OTEL_EXPORTER_OTLP_ENDPOINT set (compose jaeger profile),
  else state/runs/spans.jsonl (gitignored — OTLP is the real sink).

### 2026-07-08 — Tier 6: heartbeat, Pages, failure path

- Repo history scanned for the key (clean) before flipping to public for Pages.
- Main left unprotected so the heartbeat bot can push its commit-back; the
  alternative (data branch / bot exemption) recorded in ROADMAP blind spots.
- Container writes as root on the runner → `sudo chown` before git add (the
  classic Actions+docker gotcha).
- fail_for_demo dispatch input exists because the system is otherwise too
  resilient to demo the alert path: model sabotage just produces a fallback
  report and exits 0 — by design.
- No @claude reviews appeared on PRs #1–#7: the @claude GitHub app is not
  active on this repo (user action: /install-github-app).

### 2026-07-08 — Tier 7: overnight goal + hard lessons

- goal.md: non-enumerable target (instructor-held holdout windows), one
  checker per constraint, caps in overnight.sh not prose.
- overnight.sh reverts red iterations via checkpoint commits + git reset,
  NEVER git clean: the first version's `git clean -fd` deleted its own
  untracked goal.md/checkers mid-demo (docs/solutions/2026-07-08-git-clean-
  ate-the-loop.md). Checkpoint commits double as an audit trail.
- Anti-cheat gate compares protected files against pristine copies taken at
  loop start (not HEAD — the checkpoint commit would launder tampering).
  Demoed with a shim `claude` that sabotaged a checker and rewrote goal.md:
  both detected, restored, iteration continued green.
- check_schema initially rejected ST/EP hazards — ReliefWeb GLIDEs use the
  full GLIDE code list, not just GDACS's seven.

### 2026-07-08 — model decision closed

- User decision: production `HADR_MODEL` is **deepseek-v4-flash-free** (free
  tier; tool calls + usage verified). The kimi-k2.7-code upgrade path is
  dropped; revisiting would be a new decision.
- @claude GitHub app installed; review loop live on PRs #1–#9.

## Open questions

- Telegram or Slack for the alert webhook, and its credential (user input;
  workflow reads optional `HADR_ALERT_WEBHOOK` secret, skips if absent).
- `ISSUE_PAT` secret (fine-grained, issues:write) needed for the failure
  issue's @claude mention to actually trigger the app (user action).
- GitHub Pages enablement (Settings → Pages → Source: GitHub Actions) —
  left to the user; the heartbeat's deploy step no-ops meaningfully until then.
- ReliefWeb appname request must be filed by the user (form + email approval):
  https://apidoc.reliefweb.int/parameters#appname — do this early, approval takes time.

## Deviations

<!-- Anything built that departs from the PRD or CLAUDE.md is recorded here,
     with the reason. An undocumented deviation is a bug. -->

### 2026-07-08 — Tier 3
- The plan promised a "run history sparkline" on the ops panel; shipped a
  change-counts chip instead — same information, no chart code. Revisit if the
  panel grows in Tier 5.
