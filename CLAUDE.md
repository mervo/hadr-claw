# CLAUDE.md

Read README.md for what this project is; ROADMAP.md for tier status and known
blind spots. Keep both current in every PR — a stale doc is a bug.

## Language & tooling

- Python 3.12, managed with **uv** (`uv.lock` committed; `uv sync --frozen` in CI/containers).
- Runtime deps: `httpx` (always `follow_redirects=True` — see docs/solutions/), `feedparser`
  (ReliefWeb RSS), `openai` (Tier 4+, pointed at the OpenCode Zen base URL).
  Rendering is stdlib only (`string.Template` + `html.escape`) — no template engine.
- Canonical runtime is **docker-compose** (`docker compose run --rm claw`); `uv run`
  is the fast dev loop. Both must work for every tier's demo.
- Configuration is env-vars only. Secrets (`OPENCODE_API_KEY`, …) live in `.env`
  (gitignored) locally and GitHub Actions secrets in CI. **No secret value in any
  tracked file, doc, or note — ever.**

## Test command

- `uv run pytest` — unit tests + wrappers around the deterministic checkers.
- `uv run ruff check .` — lint.
- Deterministic checks are standalone `scripts/check_*.py`, exit 0/1, runnable
  individually (`uv run python scripts/check_dedup.py`). Anything that must give
  the same answer twice lives there, not in a prompt.
- Tests never hit the network: feed payloads are fixtures under `tests/fixtures/`;
  agent-loop tests replay recorded transcripts via `HADR_FAKE_MODEL` (no key needed).

## Conventions

- One tier = one branch = one PR = one @claude review (see ROADMAP.md).
- Conventional Commits: `feat:`, `fix:`, `docs:`, `test:`, `chore:` …
- All timestamps stored as UTC ISO8601, converted at the feed boundary and nowhere
  else; rendered as UTC + SGT side by side.
- Every string derived from a feed is `html.escape`d before rendering.
- Every HTTP fetch sends `User-Agent: hadr-claw/<version> (asr.mobilemanipulation@gmail.com)`
  and follows redirects.
- The noise filter and all thresholds: keep quakes with `mag>=4.5` OR `sig>=600`
  OR non-null PAGER alert; GDACS Orange/Red always kept; ReliefWeb entries always
  kept (human-curated). Audience is a global HADR watch floor.
- `hadr/` is the deterministic pipeline — no LLM calls in that package. LLM code
  lives in `agent/` only. Caps (turns, tokens, wall clock) are enforced in code,
  not prose.
- After Tier 6: dev PRs must not include diffs to `dashboard.html` or `state/**`
  (the heartbeat owns them; on conflict take main's version and regenerate).
- When something costs more than ten minutes, write the fix to `docs/solutions/`
  (`YYYY-MM-DD-slug.md`, frontmatter per docs/solutions/README.md). Grep that
  directory before debugging anything.
- Answers to open questions in `feeds/*.md` get recorded in those files as they
  are discovered.

## Deviations policy

Anything built that departs from problem_statement.md, ROADMAP.md or this file is recorded in
`implementation-notes.md` (Deviations section) with the reason, **before** the PR
merges. An undocumented deviation is a bug.
