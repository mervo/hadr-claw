# Roadmap

Progressive build of the HADR claw. **Every tier is end-to-end runnable and
demoable on its own** — a thin slice through fetch → assess → render, thickened
tier by tier. One tier = one branch = one PR = one @claude review.

Status values: `planned` · `in-progress` · `done`.

| # | Tier | Status | Demo | Key files |
|---|------|--------|------|-----------|
| 0 | Docs foundation | done | Read README/ROADMAP; `gh secret list` shows the key; PR raised | README.md, ROADMAP.md, CLAUDE.md, .env.example, implementation-notes.md |
| 1 | Slice one: USGS → dashboard (no LLM) | done | `docker compose run --rm claw --feeds usgs` then `docker compose up dashboard` → http://localhost:8080; offline `--fixtures`; `uv run pytest` | pyproject.toml, Dockerfile, docker-compose.yml, hadr/{__main__,events,render}.py, hadr/feeds/usgs.py, tests/ |
| 2 | All feeds + unified schema + dedup | planned | `--feeds usgs,gdacs,reliefweb` → one quake with multi-source badges; `scripts/check_dedup.py` | hadr/feeds/{gdacs,reliefweb}.py, hadr/dedupe.py, tests/fixtures/crossfeed/ |
| 3 | Memory & change detection | planned | Run twice → second run quiet; day2 fixture → ESCALATED card; `scripts/check_memory.py` | hadr/memory.py, state/seen_events.json, tests/fixtures/day2/ |
| 4 | 5-level harness (Activity 7) | planned | Chat: "check the quake feeds, write me a dashboard" → model calls tools → page updates; keyless replay via `HADR_FAKE_MODEL` | agent/{harness,tools,model}.py, agent/soul.md, tests/fixtures/transcripts/ |
| 5 | Harness as production engine + OTel | planned | `docker compose run --rm claw` (runs `agent.morning`); `HADR_MAX_TURNS=1` → fallback dashboard with degraded banner; jaeger traces at :16686 | agent/{morning,telemetry}.py, scripts/check_dashboard.py, scripts/check_spend.py |
| 6 | Heartbeat + Pages + failure path | planned | `gh workflow run heartbeat.yml && gh run watch` → Pages updates, state committed; sabotage run → issue tagging @claude; VPS: `docker compose --profile heartbeat up -d` | .github/workflows/{heartbeat,ci}.yml |
| 7 | Overnight goal (Activity 11) | planned | `scripts/run_checkers.py` all green; `overnight.sh --max-iterations 2 --dry-run` stops on cap | goal.md, scripts/overnight.sh, scripts/check_*.py |

## Decisions of record (2026-07-08)

1. **Engine**: the agentic harness drives production — the model decides when to
   call `fetch_feed`/`write_dashboard` each morning. Guardrails enforced in code;
   a deterministic fallback guarantees the report always exists. *The harness is
   the engine; the pipeline is the seatbelt.*
2. **Model API**: OpenCode Go (Zen gateway), OpenAI-compatible, env-configured.
3. **Runtime**: docker-compose is canonical for portability; `uv run` is the dev loop.
4. **Heartbeat**: GitHub Actions cron `0 0 * * *` UTC (≈08:00 SGT — drift buffer
   inside the 08:30 promise) + `workflow_dispatch`; memory committed back each run.
5. **Observability**: JSONL run records + model transcripts in `state/runs/`
   (pruned to 14), ops panel on the dashboard, OpenTelemetry traces
   (OTLP when configured, file export otherwise; jaeger compose profile).
6. **Alerting**: GitHub issue tagging @claude (via PAT, not GITHUB_TOKEN) **plus**
   a Telegram/Slack webhook. *Open: user confirms channel + credential at Tier 6.*
7. **Publishing**: repo goes public at Tier 6 (free-plan Pages requires it), after
   a full-history secret scan.
8. **Audience**: global watch-floor coverage — all GDACS Orange/Red + significant
   quakes (M≥4.5 populated / M≥6 anywhere); ReliefWeb entries kept as-is (curated).
9. **ReliefWeb**: RSS now; JSON API behind the same normalizer contract once the
   appname is approved (request to be filed — user action, form + email approval).

## Known blind spots (watch for these; move to docs/solutions/ when they bite)

**Agentic harness in production**
- The model may never call `write_dashboard`, call it twice, or with garbage →
  post-condition check + deterministic fallback after the loop.
- `write_dashboard` takes structured args keyed by event uid, never free HTML —
  facts are injected from normalized data; unknown uids rejected.
- `fetch_feed` returns normalized, filtered, size-capped JSON — never raw feeds
  (USGS all_day raw is 1–2 MB; it would blow context and spend).
- Open models emit malformed tool-call JSON more than frontier APIs: feed the
  parse error back once, then abort to fallback.
- Don't trust gateway `resp.usage` — keep a chars/4 estimator and a binding turn cap.

**GitHub Actions / Pages**
- `schedule:` and `workflow_dispatch` only fire from the default branch — the
  Tier 6 demo requires merge-then-dispatch.
- Issues created with `GITHUB_TOKEN` do **not** trigger other workflows/apps —
  the @claude failure issue must be created with a PAT (`ISSUE_PAT`).
- Pages needs one-time manual setup (Settings → Pages → Source: GitHub Actions)
  and a public repo on the free plan; first deploy can lag minutes.
- Scheduled workflows auto-disable after 60 days without repo activity; the daily
  heartbeat commit is the keep-alive, the failure issue is the alarm.
- Branch protection on main would reject the heartbeat's push — decide at Tier 6
  (exempt the bot / push state to a data branch / leave unprotected).
- Heartbeat commits carry `[skip ci]` so they don't trigger CI daily.

**Generated files in the repo**
- `dashboard.html` + `state/` are merge-conflict bait: after Tier 6, dev PRs never
  include diffs to them (take main's version, regenerate).
- The Pages artifact is canonical for readers; the committed file is the demo copy.
- Prune `state/runs/` to the last 14 runs or history bloats.

**Feed semantics**
- USGS `all_day` is a rolling window: disappearance ≠ deletion. Only a vanish
  *inside* the window is a deletion; older is silent age-out. Store `occurred_at`
  per uid to tell them apart, or every morning reports phantom deletions.
- GDACS datetimes are naive strings — treat as UTC and verify against a matching
  USGS quake once. Three feeds, three timestamp formats: normalize at the feed
  boundary, nowhere else.
- GDACS event-level vs episode-level alerts diverge: report `alertlevel`, or a
  long-running cyclone's episodes thrash the escalation detector.
- ReliefWeb RSS `pubDate` is creation-date-only — useless for change detection;
  fingerprint the description text instead. GLIDE appears in both the description
  tag and the link slug; cross-validate.
- GLIDE is often empty in fresh GDACS events — spatio-temporal matching carries
  dedup in the first 24 h; GLIDE catches ReliefWeb days later. A late source
  joining a merged cluster is UPDATED, not NEW.

**Testing the agent loop**
- Recorded transcripts go stale when tool schemas change — embed a schema hash in
  each fixture and assert it on replay. Keep exactly one live smoke test
  (dispatch-only, never in PR CI).

**Process**
- Verify Zen model ids + endpoint with a 5-line curl before building the harness.
- Heartbeat (production) and any overnight loop (development) may both write the
  repo the same night — the overnight loop works on a branch, never main.
