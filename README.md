# HADR Claw

A monitoring agent ("claw") for humanitarian assistance and disaster response (HADR).
It watches live disaster feeds — [GDACS](feeds/gdacs.md), [USGS earthquakes](feeds/usgs.md)
and [ReliefWeb](feeds/reliefweb.md) — filters the noise, assesses what remains
(what happened, where, how bad, who is affected), and publishes a morning situation
report to `dashboard.html` at **08:30 Singapore time**, unattended, staying quiet when
nothing has changed.

> **Status: Tier 4 — the claw has a brain.** On top of the Tier 1–3 pipeline
> (three feeds → unified events → dedup → memory diff → dashboard), there is now
> a hand-built agent harness (`agent/harness.py`, ~80 lines): the model decides
> when to call `fetch_feed` and `write_dashboard`, with a turn cap and uid
> validation so it cannot invent events. Production wiring lands in Tier 5.
> See [ROADMAP.md](ROADMAP.md) for the tier-by-tier build plan; each tier is
> end-to-end runnable and demoable. This README grows with each tier and never
> describes features that don't exist yet.

## What's a claw?

A claw is a small, always-on agent that is mostly files and a loop. Its six parts,
mapped to this repository (see [Goal.md](Goal.md) for the course brief):

| Part | What it is | Where it lives here |
|------|-----------|---------------------|
| **Soul** | Standing orders: what the agent is for, how it behaves | `CLAUDE.md` (dev conventions) + `agent/soul.md` (runtime system prompt, Tier 4) |
| **Loop** | Code that feeds the model context, runs its tools, goes round again | `agent/harness.py` (~100-line agent loop, Tier 4) |
| **Tools** | Bounded actions run on the model's behalf | `fetch_feed`, `write_dashboard` (`agent/tools.py`, thin wrappers over `hadr/`) |
| **Memory** | What survives between runs, in files not prompts | `state/seen_events.json` — which events it has already assessed (Tier 3) |
| **Heartbeat** | The schedule that wakes it without a human | GitHub Actions cron, 00:00 UTC daily (Tier 6); docker-compose `heartbeat` profile for VPS hosting |
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
docker compose run --rm claw    # fetch all feeds, dedup, write dashboard.html
docker compose up dashboard     # serve it at http://localhost:8080/dashboard.html
```

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
- [ ] **Tier 5** — `docker compose run --rm claw` → full agentic morning report;
  `docker compose --profile observability up` → traces at http://localhost:16686
- [ ] **Tier 6** — `gh workflow run heartbeat.yml` → unattended run, dashboard on
  GitHub Pages
- [ ] **Tier 7** — `bash scripts/overnight.sh` → capped overnight improvement loop

Tests and lint (from Tier 1): `uv run pytest` · `uv run ruff check .`

## Configuration & secrets

All configuration is environment variables; **no secret value ever appears in a
tracked file**. Copy `.env.example` to `.env` (gitignored) and fill it in:

| Variable | Purpose |
|----------|---------|
| `OPENCODE_API_KEY` | OpenCode Go key (get one at opencode.ai — subscribe to Go). Also stored as a GitHub Actions secret of the same name for scheduled runs. |
| `HADR_MODEL_BASE_URL` | OpenAI-compatible base URL. Default `https://opencode.ai/zen/v1` |
| `HADR_MODEL` | Model id on the gateway. Default `deepseek-v4-flash-free` (free tier, tool calls verified); production candidate `kimi-k2.7-code` needs workspace balance — see docs/solutions/2026-07-08-zen-gateway-models.md |
| `HADR_MAX_TURNS` / `HADR_MAX_TOKENS_TOTAL` | Hard caps on the agent loop, enforced in code |
| `HADR_FAKE_MODEL` | Path to a recorded transcript — replays the agent loop with no key (used by CI) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Optional; when set, traces export via OTLP (e.g. to the compose jaeger) |

GitHub Actions gets the key once via `gh secret set OPENCODE_API_KEY`; workflows
reference `${{ secrets.OPENCODE_API_KEY }}`.

## The feeds

| Feed | What | Access | Notes |
|------|------|--------|-------|
| [USGS](feeds/usgs.md) | Real-time earthquakes, GeoJSON, rolling windows | Open | Events get revised/deleted after publication |
| [GDACS](feeds/gdacs.md) | Multi-hazard (EQ/TC/FL/VO/DR/WF) with colour alert levels | Open | Alert levels can escalate after first report |
| [ReliefWeb](feeds/reliefweb.md) | Curated humanitarian disasters (UN OCHA) | RSS open; JSON API needs a pre-approved appname | We build against RSS; appname request should be filed early (approval takes time) |

## Repository map

```
Goal.md                  # course brief (untouched) — what this claw must become
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
