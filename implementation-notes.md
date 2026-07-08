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

## Open questions

- Telegram or Slack for the alert webhook, and its credential (user input, Tier 6).
- Exact `HADR_MODEL` id on the Zen catalog — verify with curl at Tier 4 start.
- ReliefWeb appname request must be filed by the user (form + email approval):
  https://apidoc.reliefweb.int/parameters#appname — do this early, approval takes time.
- Does Zen populate `resp.usage` for the chosen model? Determines whether the
  token cap uses real usage or the chars/4 estimator (Tier 4).

## Deviations

<!-- Anything built that departs from the PRD or CLAUDE.md is recorded here,
     with the reason. An undocumented deviation is a bug. -->

### 2026-07-08 — Tier 3
- The plan promised a "run history sparkline" on the ops panel; shipped a
  change-counts chip instead — same information, no chart code. Revisit if the
  panel grows in Tier 5.
