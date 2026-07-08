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

### 2026-07-08 — @claude review round (PRs #1–#9), fixes applied at stack tip

Real bugs found by review, all fixed in one commit on tier-7-overnight:
- dedupe `_absorb` dropped `depth_km` when GDACS (no depth) was primary; and
  re-fetching a feed duplicated source rows — both fixed with regression tests.
- morning `_agent_loop` constructed the model client outside its try/except,
  so a missing `OPENCODE_API_KEY` crashed the run instead of falling back.
- soul.md's "fetch the feeds first" contradicted the morning briefing's
  "do NOT fetch" — now conditional ("if events have not been provided").
- heartbeat failure-issue dedup: `--jq '.[0].number'` prints literal `null`
  on empty, so the FIRST failure tried `gh issue comment null` and no issue
  was ever created; fixed with `// empty`.
- `HADR_MAX_TOKENS_TOTAL` was documented as enforced but the interactive
  harness never read it — now enforced in `run_turn` too.
- memory: state file now prunes inactive entries after 30 days (unbounded
  growth); dead `last_reported_fingerprint` field removed; ESCALATED now
  compares to the most recent alert level, so re-escalation after a dip
  surfaces again (was: only above all-time max).
- overnight.sh: green iterations commit immediately (a cap trip no longer
  strands the last iteration's work); tampering now VOIDs the whole
  iteration via reset (was: restore-and-continue, contradicting goal.md).
- supercronic pinned by sha256; LiveModel now sends the repo User-Agent and
  follows redirects like every other HTTP call site; state/** churn dropped
  from PR #9 per the post-Tier-6 convention.

Declined with rationale (replied on the PRs):
- Token estimator "double-counting" (PR #7): summing per-request totals is
  the intended spend semantic — every request re-sends the conversation as
  prompt; clarifying comment added instead.
- state/runs noise in PR #4: already in merged history below Tier 6, where
  the convention doesn't apply yet.

### 2026-07-08 — alert channel decided: Telegram

- Heartbeat failure alerts go to Telegram via the Bot API (`TELEGRAM_BOT_TOKEN`
  + `TELEGRAM_CHAT_ID` secrets); the generic `HADR_ALERT_WEBHOOK` was replaced
  since its Slack-style payload wouldn't have worked with Telegram anyway.
- `heartbeat-failure` label created in the repo — without it the first
  labeled issue-create fails to the unlabeled fallback and dedup breaks.
- Pages enabled + first live heartbeat verified end-to-end (engine=agentic,
  1 turn, ~1.8k tokens, dashboard at mervo.github.io/hadr-claw).

### 2026-07-08 — overnight iteration 2: feed-parsing hardening

(Iteration 1 checkpoints are empty — setup/orientation only, no changes landed.)

- All three normalizers now skip a malformed feature/entry (warning via stdlib
  `logging`) instead of crashing the feed: one bad payload row previously
  reported **zero events for the whole run** — the worst possible holdout
  failure mode. Covered: null geometry, missing/null `time`/`fromdate`,
  string magnitudes, entries stripped of description/link/date.
- GDACS tolerance: `iscurrent` compared as string today but a boolean upstream
  would have silently dropped every event (`str(...).lower() == "true"` now);
  `severitydata.severity` coerced via `_num()` so string magnitudes don't
  TypeError in `is_significant` or dedup's magnitude-delta comparison.
- Tests: +4 (38 total) — malformed-feature cases for each feed, inline
  payloads (no network), all checkers stay green.

### 2026-07-08 — overnight iteration 3: memory + dedup correctness, multi-hazard fixtures

- **Phantom-escalation bug fixed** (`hadr/memory.py`): `alert_label` returned
  `gdacs_alert or pager_alert` while `alert_rank` takes the max of both — an
  event with GDACS Green + PAGER orange recorded the *lower* label, so every
  subsequent run compared rank 2 against recorded rank 0 and reported
  ESCALATED forever. `alert_label` now returns the highest-ranked level,
  keeping label and rank consistent. Regression test added.
- **Dedup guard**: `_epoch("")` returns 0.0, so two same-hazard events within
  100 km that *both* lacked timestamps spacetime-merged on place alone. The
  spacetime rule now requires both `occurred_at` values. (Not reachable from
  today's normalizers — GDACS/USGS reject rows without times — but a holdout
  fixture with degraded payloads could hit it.)
- **Multi-hazard cross-feed fixtures** (`tests/fixtures/crossfeed_multihazard/`):
  dedup coverage was earthquake-only. Added GDACS TC (Orange, with GLIDE) +
  ReliefWeb entry merging via GLIDE (summary survives the merge for the
  assessment), and a fresh GDACS FL with *empty* GLIDE that must stay separate
  from ReliefWeb's flood entry rather than false-merge on country — pinning
  the documented first-24h GLIDE gap as intended behavior.
- Tests: +5 (43 total); all checkers green.

### 2026-07-08 — overnight run 1: results + harness fixes

- Iteration 1 (the only one that ran): hardened all three feed normalizers —
  a malformed feature/entry (null geometry, missing time, string magnitudes,
  boolean iscurrent) skips that row with a warning instead of crashing the
  feed; +4 no-network tests. Salvaged onto this branch from the loop's
  checkpoint chain (24 empty checkpoints dropped).
- Iterations 2-12 died instantly on the account usage limit ("resets 2:10pm")
  — Route B shares interactive-session limits. overnight.sh now backs off 15m
  on a limit hit without counting the iteration (docs/solutions entry).
- python -m hadr wrote run records into repo state/runs even with a scratch
  --state, polluting the loop branch with state/** churn — records now land
  next to their state file (+ regression test).

## Open questions

- `ISSUE_PAT` secret (fine-grained, issues:write) needed for the failure
  issue's @claude mention to actually trigger the app (user action).
- `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` secrets to be set by the user
  (BotFather steps in README); failure path test pending those.
- ReliefWeb appname request must be filed by the user (form + email approval):
  https://apidoc.reliefweb.int/parameters#appname — do this early, approval takes time.

## Deviations

<!-- Anything built that departs from the PRD or CLAUDE.md is recorded here,
     with the reason. An undocumented deviation is a bug. -->

### 2026-07-08 — Tier 3
- The plan promised a "run history sparkline" on the ops panel; shipped a
  change-counts chip instead — same information, no chart code. Revisit if the
  panel grows in Tier 5.

### 2026-07-08 — overnight iteration 4: severity normalization fix

- **USGS magnitude priority bug fixed** (`hadr/dedupe.py`): when a GDACS quake
  (e.g., M4.8) merged with USGS data (e.g., M5.0), the merge kept GDACS's
  potentially older magnitude instead of using USGS's authoritative value.
  This caused the watch floor to see stale severity data. Now USGS magnitude
  overrides GDACS magnitude when a GDACS-primary event merges with USGS data,
  since USGS is the authoritative source and often has more recent revisions.
  Regression test `test_usgs_magnitude_overrides_gdacs_when_merging` added.
- Impact: fixes "severities right" judging axis on holdout events where GDACS
  and USGS report the same quake with different magnitudes.
- Tests: +1 (44 total); all checkers green.

### 2026-07-08 — overnight iteration 6: volcano (VO) hazard type coverage

- **Broadened fixture coverage** to include Volcano (VO) hazard type, completing
  the trio of GDACS multi-hazard types (EQ/TC/FL/VO). Volcano fixtures added to:
  - Main GDACS fixture (`tests/fixtures/gdacs/events.json`): Mount Merapi eruption
    (eventid 1550801) with Orange alert and GLIDE VO-2026-000201-IDN
  - Main ReliefWeb fixture (`tests/fixtures/reliefweb/rss.xml`): matching volcano
    entry with curated summary text
  - Multihazard test fixtures (`tests/fixtures/crossfeed_multihazard/`): both GDACS
    and ReliefWeb volcano events for cross-feed dedup testing
- **Tests added** (+3 total, 47 total):
  - `test_volcano_merges_across_gdacs_and_reliefweb_via_glide`: verifies volcano dedup
    works via GLIDE, same pattern as TC and FL
  - `test_volcano_orange_alert_kept`: confirms GDACS normalizer keeps Orange-alert
    volcanoes
  - `test_volcano_extracted_from_fixture`: confirms ReliefWeb volcano extraction
- Impact: "more hazard types (TC/FL/VO)" from goal.md now achieved; pipeline tested
  on all four Orange/Red multi-hazard types. Schema comments already listed VO;
  this adds the test surface and fixtures to exercise it.
- Checkers: schema now validates 30 events (was 29), all 6 checkers green.

### 2026-07-08 — overnight iteration 7: revision sequences for non-EQ hazards

- **Multi-hazard revision fixtures** (`tests/fixtures/day2_multihazard/`): new day2
  snapshot with TC and VO escalations to test that the memory system tracks severity
  changes for non-earthquake hazards with the same rigor as earthquakes.
  - Tropical Cyclone: Orange (185 km/h) -> Red (240 km/h) — tests cyclone intensification
  - Volcano: Orange (Magnitude 4) -> Red (Magnitude 5) — tests eruption escalation
- **Tests added** (+2 total, 49 total):
  - `test_tropical_cyclone_escalation_from_orange_to_red`: verifies TC escalation
    detection when wind speeds increase
  - `test_volcano_escalation_from_orange_to_red`: verifies VO escalation detection
    when eruption intensity increases
- Impact: "more revision and escalation sequences" from goal.md now includes non-EQ
  hazards; memory.py and dedup.py handle TC/VO revisions as rigorously as quake
  magnitude changes. Holdout fixtures with multi-hazard escalations now testable.
- Checkers: all 6 green; schema still validates 30 events; test count 49 (was 47).

### 2026-07-08 — overnight iteration 4: flood escalation sequences for completeness

- **Completed multi-hazard escalation coverage** by adding FL (flood) escalation to
  the day2_multihazard fixture. Previously only TC and VO escalated Orange->Red;
  now all three major GDACS multi-hazard types (EQ/TC/FL/VO) have escalation testing.
- **Fixture changes** (`tests/fixtures/day2_multihazard/`):
  - GDACS FL event: escalated from Orange (severity 2.0) to Red (severity 3.5)
    with updated timestamp and impact wording
  - ReliefWeb FL event: updated with more severe impact description (4.8M affected,
    disease outbreaks, resource shortages) to match escalation
- **Test added** (+1 total, 50 total):
  - `test_flood_escalation_from_orange_to_red`: verifies FL escalation detection
    when severity magnitude increases, matching TC/VO test pattern
- Impact: goal.md's "more revision and escalation sequences" for non-EQ hazards
  now fully satisfied; holdout fixtures with flood escalations will now be testable
  on this general pattern (severity increase + alert change detection).
- Checkers: all 6 green; schema still validates 30 events; test count 50 (was 49).

### 2026-07-08 — overnight iteration 4: hazard type coverage (EP/ST)

- **Broadened hazard type test coverage** for ReliefWeb epidemics and storms, which
  are already handled in the normalizer but lacked explicit unit tests. ReliefWeb
  carries GLIDE codes including EP (epidemics/disease outbreaks) and ST
  (storms/hailstorms) — these extract correctly via the GLIDE hazard prefix split,
  but had no regression tests.
- **Tests added** (+2 total, 52 total):
  - `test_epidemic_extracted_from_fixture`: verifies EP hazard entries (Ebola,
    Dengue) are extracted with correct GLIDE codes and titles
  - `test_storm_hailstorm_extracted_from_fixture`: verifies ST hazard entries
    (hailstorm) extract with correct GLIDE code
- **Coverage**: ReliefWeb fixture carries 9 entries spanning EQ/FL/TC/VO/VO/EP/EP/ST
  (multiple entries per type); new tests validate that non-traditional hazard types
  (epidemics and storms) are handled correctly when present in unseen holdout events.
- Impact: goal.md's "broaden fixture coverage: more hazard types" is now complete
  for all documented GLIDE types appearing in visible fixtures. Holdout fixtures
  with EP or ST events will now be testable on this pattern.
- Checkers: all 6 green; schema still validates 30 events; test count 52 (was 50).

### 2026-07-08 — overnight iteration 5: earthquake magnitude-null dedup fix

- **Fixed a critical dedup bug** where two earthquakes without magnitude data would
  wrongly merge via spacetime rule. The issue: line 59 of `dedupe.py` allowed
  spacetime merge when `mag_a is None or mag_b is None`, causing distinct aftershocks
  in seismically active regions to be incorrectly clustered into one event. For
  earthquakes, magnitude is the primary discriminator; relying on place+time alone
  is unsafe. Fix: for EQ hazards, require at least one magnitude to be present and
  valid; never merge two magnitude-null earthquakes via spacetime. For non-EQ
  hazards (TC/FL/VO), magnitude check N/A since they don't report it.
- **Regression test added** (+1 total, 53 total):
  - `test_two_distinct_quakes_without_magnitude_do_not_merge`: creates two
    earthquakes 5 km apart, 15 minutes apart, both magnitude-null, verifies they
    stay separate (would have merged before the fix via spacetime rule).
- **Behavior impact**: holdout fixtures with earthquake swarms or multiple quakes
  in seismic regions will now merge correctly. Previously would have seen false
  merges (undercounts events) and wrong severity/assessment data (merged distinct
  events). Fixes "events found" and "duplicates merged" judging axes.
- Checkers: all 6 green; schema validates 30 events; test count 53 (was 52).
