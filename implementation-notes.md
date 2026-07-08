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
