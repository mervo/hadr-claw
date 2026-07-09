# HADR Claw

A monitoring agent ("claw") for humanitarian assistance and disaster response (HADR).
It watches live disaster feeds — [GDACS](feeds/gdacs.md), [USGS earthquakes](feeds/usgs.md)
and [ReliefWeb](feeds/reliefweb.md) — filters the noise, assesses what remains
(what happened, where, how bad, who is affected), and publishes a morning situation
report to `dashboard.html` at **08:30 Singapore time**, unattended, staying quiet when
nothing has changed.

> **Status: all seven tiers built.** Deterministic pipeline (three feeds →
> dedup → memory) + agentic morning engine with code-enforced caps and a
> fallback that guarantees the report always exists + Actions heartbeat with
> Pages publishing and @claude failure alerts + a capped, tamper-proof
> overnight improvement loop. Awaiting: @claude app install, PR reviews, and
> the merge to main that arms the heartbeat (see ROADMAP.md → Launch).
> See [ROADMAP.md](ROADMAP.md) for the tier-by-tier build plan; each tier is
> end-to-end runnable and demoable. This README grows with each tier and never
> describes features that don't exist yet.

## What's a claw?

A claw is a small, always-on agent that is mostly files and a loop. Its six parts,
mapped to this repository (see [problem_statement.md](problem_statement.md) for the course brief):

| Part | What it is | Where it lives here |
|------|-----------|---------------------|
| **Soul** | Standing orders: what the agent is for, how it behaves | `CLAUDE.md` (dev conventions) + `agent/soul.md` (runtime system prompt, Tier 4) |
| **Loop** | Code that feeds the model context, runs its tools, goes round again | `agent/harness.py` (~100-line agent loop, Tier 4) |
| **Tools** | Bounded actions run on the model's behalf | `fetch_feed`, `write_dashboard` (`agent/tools.py`, thin wrappers over `hadr/`) |
| **Memory** | What survives between runs, in files not prompts | `state/seen_events.json` — which events it has already assessed (Tier 3) |
| **Heartbeat** | The schedule that wakes it without a human | GitHub Actions cron, 00:07 UTC daily (Tier 6); docker-compose `heartbeat` profile for VPS hosting |
| **Channel** | Where output lands so someone can act on it | `dashboard.html`, published via GitHub Pages (Tier 6) |

## Architecture at a glance

- **Deterministic pipeline** (`hadr/`): fetch → normalize to a unified event schema →
  cross-feed dedup → diff against memory. No LLM in this layer; it is fully testable
  offline against fixtures.
- **Agentic engine** (`agent/`): a hand-built agent loop drives the morning run — the
  model decides when to call `fetch_feed` and `write_dashboard`. Guardrails are
  enforced in code (turn/token/wall-clock caps, structured tool arguments, unknown
  event ids rejected), and a deterministic fallback renderer guarantees **the morning
  report always exists** even when the model misbehaves.
- **Model API**: OpenCode Go (OpenCode Zen gateway), OpenAI-compatible endpoint.
  Configured entirely via environment variables — see Configuration below.
- **Runtime**: docker-compose is the canonical, portable way to run the system;
  bare `uv run` is the fast inner dev loop.
- **Observability**: JSONL run records + per-run model transcripts in `state/runs/`,
  an ops panel on the dashboard itself, and OpenTelemetry traces (jaeger available
  as a compose profile).

## Running it

```sh
docker compose run --rm claw    # the full morning run: fetch, diff, assess, write
docker compose up dashboard     # serve it at http://localhost:8080/dashboard.html
```

Pipeline-only (no model, no key): `docker compose run --rm claw -m hadr`.
Traces: `docker compose --profile observability up -d jaeger`, then run claw with
`-e OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318` → http://localhost:16686
(without an endpoint, spans land in `state/runs/spans.jsonl`).

Dev loop without docker: `uv run python -m hadr` (or `--feeds usgs` for one feed).
Offline/deterministic (used by tests and CI): add `--fixtures tests/fixtures`.
Each run appends a record to `state/runs/` (pruned to the newest 14) — feed health,
latency, event counts; the dashboard's ops strip shows the same at a glance.

The interface per tier (kept current as tiers land — unchecked means not built yet):

- [x] **Tier 1** — `docker compose run --rm claw --feeds usgs` then
  `docker compose up dashboard` → http://localhost:8080/dashboard.html
  (dev loop: `uv run python -m hadr --feeds usgs`; offline: `--fixtures tests/fixtures`)
- [x] **Tier 2** — `--feeds usgs,gdacs,reliefweb` (the default) → merged
  multi-source events; `uv run python scripts/check_dedup.py` proves the merge
- [x] **Tier 3** — run twice → second run reports "no new developments";
  escalations (Green→Orange→Red) surface above the fold; USGS deletions inside
  the 24 h window are flagged, older disappearances age out silently;
  `uv run python scripts/check_memory.py` proves all of it
- [x] **Tier 4** — `uv run python agent/harness.py` → chat with the agent; it
  calls the tools itself ("check the quake feeds and write me a dashboard").
  Keyless replay: `HADR_FAKE_MODEL=tests/fixtures/transcripts/report.json …`;
  record new transcripts with `--record <path>` on a live run
- [x] **Tier 5** — `docker compose run --rm claw` → full agentic morning report;
  kill-switch demo: `HADR_MAX_SECONDS=0 uv run python -m agent.morning` → the
  cap trips and the deterministic fallback report still exists;
  `scripts/check_dashboard.py` + `scripts/check_spend.py` are the instruments
- [x] **Tier 6** — `gh workflow run heartbeat.yml && gh run watch` → unattended
  run: morning report, memory committed back, dashboard published to GitHub
  Pages. Failure demo: `gh workflow run heartbeat.yml -f fail_for_demo=true`
  → issue tagging @claude. VPS alternative:
  `docker compose --profile heartbeat up -d` (supercronic, same schedule)
- [x] **Tier 7** — `bash scripts/overnight.sh` → capped overnight improvement
  loop (Route B): `claude -p` per iteration against `goal.md`, pristine-copy
  checkers, checkpoint-commit reverts, hard caps in code. Demo without spend:
  `bash scripts/overnight.sh --max-iterations 2 --dry-run`; all instruments:
  `uv run python scripts/run_checkers.py`

Tests and lint (from Tier 1): `uv run pytest` · `uv run ruff check .`

## Example: from feed to report

**Input** — three feeds report the same physical earthquake, days apart, under
different identifiers (abridged; full samples in `feeds/*.md`):

```jsonc
// USGS all_day.geojson — minutes after the quake
{"id": "us7000ven1", "properties": {"mag": 7.1, "place": "25 km NNW of Moron, Venezuela",
 "time": 1782310260000, "alert": "orange", "sig": 900, "ids": ",us7000ven1,"}}

// GDACS geteventlist — the same quake, its own id, no depth
{"properties": {"eventtype": "EQ", "eventid": 1550999, "alertlevel": "Red",
 "glide": "EQ-2026-000093-VEN", "fromdate": "2026-06-24T14:11:02", "source": "NEIC"}}
```
```xml
<!-- ReliefWeb RSS — days later, human-curated -->
<item><title>Venezuela: Earthquakes - Jun 2026</title>
  <link>https://reliefweb.int/disaster/eq-2026-000093-ven</link> …</item>
```

**Normalized + deduplicated** — one `Event`, three audited sources
(`uv run python -m hadr --fixtures tests/fixtures/crossfeed`):

```jsonc
{"uid": "glide:EQ-2026-000093-VEN", "hazard": "EQ",
 "title": "Earthquake in Venezuela", "occurred_at": "2026-06-24T14:11:02Z",
 "lat": 10.62, "lon": -68.28, "depth_km": 10.0,          // depth kept from USGS
 "severity": {"gdacs_alert": "Red", "mag": 7.1, "pager_alert": "orange"},
 "glide": "EQ-2026-000093-VEN",
 "sources": [
   {"feed": "gdacs", "id": "1550999"},                        // merge primary
   {"feed": "usgs", "id": "us7000ven1", "merged_by": "spacetime"},
   {"feed": "reliefweb", "id": "EQ-2026-000093-VEN", "merged_by": "glide"}]}
```

**Assessment** — the morning engine briefs the model with the memory diff
(counts + the new/escalated events above); the model answers with one
structured tool call, never free HTML:

```jsonc
write_dashboard({"headline": "Red-alert M7.1 earthquake near Moron, Venezuela",
  "overview": "Two strong earthquakes struck north-central Venezuela …",
  "assessments": [{"uid": "glide:EQ-2026-000093-VEN", "priority": "high",
    "assessment": "M7.1 at 10 km depth near populated Carabobo State; GDACS Red …"}]})
```

Facts (magnitude, place, links) are injected from the normalized data by uid —
unknown uids are rejected, so the model cannot invent events.

**Output** — three artifacts per run:

- [`dashboard.html`](https://mervo.github.io/hadr-claw/) — the situation
  report: freshness stamp (UTC + SGT), ops strip (feed health/latency, change
  counts), then Escalated / New / Updated / Ongoing cards with the model's
  assessment on each.
- `state/runs/<stamp>.json` — the run record (a real one):
  ```json
  {"engine": "agentic", "turns": 1, "tokens": 1783, "cap_tripped": null,
   "duration_ms": 7948, "changes": {"new": 1, "escalated": 0, "updated": 1,
   "unchanged": 40, "deleted": 0}}
  ```
  plus `<stamp>-transcript.json`, the full model conversation for audit.
- Console: `engine=agentic events=42 turns=1 tokens=1783 cap=None -> dashboard.html`

On a morning where nothing changed, the report still publishes — fresh stamp,
"No new developments since <date>" — and the model is never called
(`engine=pipeline-quiet`, zero tokens).

## Configuration & secrets

All configuration is environment variables; **no secret value ever appears in a
tracked file**. Copy `.env.example` to `.env` (gitignored) and fill it in:

| Variable | Purpose |
|----------|---------|
| `OPENCODE_API_KEY` | OpenCode Go key (get one at opencode.ai — subscribe to Go). Also stored as a GitHub Actions secret of the same name for scheduled runs. |
| `HADR_MODEL_BASE_URL` | OpenAI-compatible base URL. Default `https://opencode.ai/zen/v1` |
| `HADR_MODEL` | Model id on the gateway. **Production model: `deepseek-v4-flash-free`** (decided 2026-07-08 — free tier, tool calls and usage reporting verified; see docs/solutions/2026-07-08-zen-gateway-models.md) |
| `HADR_MAX_TURNS` / `HADR_MAX_TOKENS_TOTAL` | Hard caps on the agent loop, enforced in code |
| `HADR_FAKE_MODEL` | Path to a recorded transcript — replays the agent loop with no key (used by CI) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Optional; when set, traces export via OTLP (e.g. to the compose jaeger) |

GitHub Actions gets the key once via `gh secret set OPENCODE_API_KEY`; workflows
reference `${{ secrets.OPENCODE_API_KEY }}`.

Three more secrets unlock the full alerting path (all optional — the heartbeat
degrades gracefully without them):

- `ISSUE_PAT` — a fine-grained PAT with issues:write. Failure issues created
  with the default `GITHUB_TOKEN` do **not** trigger the @claude app; a PAT
  makes the `@claude investigate` mention actually summon it.
- `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` — failures also ping a Telegram
  chat via the Bot API. One-time setup: create a bot with @BotFather
  (`/newbot` → copy the token), send the bot any message, then read your chat
  id from `https://api.telegram.org/bot<TOKEN>/getUpdates`
  (`.result[0].message.chat.id`).

## How it's hosted and runs

**The short answer:** GitHub Actions runs your claw on their servers at 00:07 UTC daily. You don't need your laptop powered on; GitHub provides the compute. The workflow is in `.github/workflows/heartbeat.yml`.

No server. Four free/cheap services each play one part of the claw's anatomy:

```
             GitHub Actions (cron 00:07 UTC + workflow_dispatch)   ← heartbeat
                  │  runs `docker compose run --rm claw`
                  ▼
             agent/morning.py in the project container             ← loop
              │ fetch USGS/GDACS/ReliefWeb (hadr/, deterministic)  ← tools
              │ dedup across feeds, diff vs state/seen_events.json ← memory
              │ model assesses via OpenCode Zen (OpenAI-compatible)
              │ write dashboard (structured args; fallback if model fails)
              ▼
   git commit state/ + dashboard.html back to main   [runner is wiped;
                  │                                    memory survives in git]
                  ▼
             GitHub Pages ← https://mervo.github.io/hadr-claw/     ← channel
```

**Key detail:** GitHub Actions runners are wiped after each run, so memory survives only because the workflow commits `state/seen_events.json` back to the repo. On the next run, the workflow checks out your repo again, which includes the memory from the previous run.

### Free Tier Constraints

The free tier has limits you should monitor:

- **Actions minutes:** 2,000 min/month across all your repos. One morning run takes ~10 min; at once daily (30 days), you use ~300 min. ✓ Well under budget. Monitor at `github.com/settings/billing/summary`. If you add more scheduled runs, budget accordingly.
- **Concurrent jobs:** 1 per repo. If you trigger a manual run while the cron is already queued, it waits. Don't spam `gh workflow run`; each run costs 10 minutes.
- **API rate limits:** Authenticated requests = 5,000/hour. Each morning run makes ~5–10 GitHub API calls (git push, issue creation, Pages publish). ✓ Not a concern at once daily.
- **External API (OpenCode key):** Check your OpenCode account for limits on the Zen gateway. The workflow has a **10-minute timeout** + token caps in the claw code to prevent runaway spend.
- **Secrets:** Store `OPENCODE_API_KEY` only in GitHub Secrets, never in `.env` or tracked files. Rotate the key periodically if it was shared in chat or logs.

**The upshot:** At one run per day with the current setup, the free tier is fine. You have room to expand to multiple runs per day before hitting any hard limits.

**The daily lifecycle** (`.github/workflows/heartbeat.yml`):

1. Cron fires at **00:07 UTC / 08:07 SGT** — buffer inside the 08:30 SGT
   promise, because Actions cron can drift 15+ minutes.
2. The runner checks out the repo and runs the **same compose service used in
   dev** (`docker compose run --rm claw`) with `OPENCODE_API_KEY` from the
   Actions secret store, under a 10-minute `timeout` on top of the in-code caps.
3. `scripts/check_dashboard.py` + `check_spend.py` gate the result — a report
   that fails its checks never publishes.
4. `state/` + `dashboard.html` are committed back to main (`[skip ci]`,
   rebase-retry ×3) — the runner is wiped after every run, so **the repo is the
   claw's memory**. The daily commit doubles as the keep-alive that stops
   GitHub auto-disabling the cron after 60 idle days.
5. `dashboard.html` deploys to **GitHub Pages** as `index.html` — the published
   artifact is canonical for readers; the committed file is the demo copy.
   (After Tier 6, dev PRs must not diff `dashboard.html`/`state/**` — take
   main's version and regenerate.)
6. **Quiet mornings still publish** — fresh stamp, "no new developments" lead,
   zero model tokens; a page that never changes is indistinguishable from a
   dead one.

**When a run fails** (verified live with `workflow_dispatch` +
`fail_for_demo=true`):

- An issue labeled `heartbeat-failure` opens, tagging **@claude** to
  investigate, with the run URL. Repeat failures comment on the open issue
  instead of piling up new ones. (The mention only *summons* the app when the
  issue is created with `ISSUE_PAT`; with the fallback `GITHUB_TOKEN` the
  issue still exists but the app isn't triggered.)
- A **Telegram** message hits the configured chat via the Bot API
  (`TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` secrets).
- The morning report itself degrades before it dies: model failure or a
  tripped cap produces the deterministic fallback dashboard with a banner,
  and a feed outage produces a partial report with a per-feed banner — a
  workflow failure means something worse than both.

**Alternative hosts** (same image, no code changes):

- **Any Docker host / VPS**: `docker compose --profile heartbeat up -d` runs
  supercronic on the same 00:07 UTC schedule; state persists on disk via the
  bind mount, no commit-back needed.
- **Laptop**: `docker compose run --rm claw` whenever you want a report
  (remember the lid-closed problem — this is for dev, not the promise).

## The feeds

| Feed | What | Access | Notes |
|------|------|--------|-------|
| [USGS](feeds/usgs.md) | Real-time earthquakes, GeoJSON, rolling windows | Open | Events get revised/deleted after publication |
| [GDACS](feeds/gdacs.md) | Multi-hazard (EQ/TC/FL/VO/DR/WF) with colour alert levels | Open | Alert levels can escalate after first report |
| [ReliefWeb](feeds/reliefweb.md) | Curated humanitarian disasters (UN OCHA) | RSS open; JSON API needs a pre-approved appname | We build against RSS; appname request should be filed early (approval takes time) |

## Repository map

```
problem_statement.md                  # course brief (untouched) — what this claw must become
ROADMAP.md               # tier table with live status + known blind spots
CLAUDE.md                # conventions for agents & humans working on this repo
implementation-notes.md  # decisions / open questions / deviations, per working block
hadr/                    # deterministic pipeline: feeds/ → events → render (no LLM here)
tests/                   # pytest + fixtures (checked-in feed payloads; never the network)
state/seen_events.json   # memory: what the claw has already assessed (committed)
state/runs/              # per-run observability records (newest 14 kept)
dashboard.html           # the channel: generated situation report
feeds/                   # per-feed endpoint docs and open questions
docs/solutions/          # one hard-won fix per file; grep before debugging
scripts/                 # deterministic checks (exit 0/1); later the goal-file checkers
skills/                  # project skills, one folder per skill
```

## Conventions (summary — full version in CLAUDE.md)

- One tier = one branch = one PR = one @claude review.
- Conventional Commits (`feat:`, `fix:`, `docs:` …).
- Every PR keeps README, ROADMAP, CLAUDE.md, implementation-notes and feeds/*.md
  current — stale docs are treated as bugs.
- Anything that cost more than ten minutes to figure out gets a file in
  `docs/solutions/`.
