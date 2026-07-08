"""Production entry: the heartbeat runs this every morning.

Deterministic pre-work (fetch, dedup, memory diff) feeds one briefing to the
agentic harness; the model assesses and calls write_dashboard. Caps on turns,
tokens and wall clock are enforced here, in code — and if the loop ends
without a valid dashboard for any reason, a deterministic fallback renders
one. The morning report can never fail to exist.

    uv run python -m agent.morning [--fixtures DIR] [--out dashboard.html]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent import tools  # noqa: E402
from agent.harness import SOUL  # noqa: E402
from agent.model import make_model  # noqa: E402
from agent.telemetry import tracer  # noqa: E402
from hadr import dedupe, memory, render  # noqa: E402
from hadr.__main__ import FEEDS, gather  # noqa: E402
from hadr.runlog import write_run  # noqa: E402

MAX_TURNS = int(os.environ.get("HADR_MAX_TURNS", "12"))
MAX_TOKENS = int(os.environ.get("HADR_MAX_TOKENS_TOTAL", "150000"))
MAX_SECONDS = int(os.environ.get("HADR_MAX_SECONDS", "300"))


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _briefing(changes) -> str:
    def brief(e):
        return {
            "uid": e.uid, "hazard": e.hazard, "title": e.title, "country": e.country,
            "occurred_at": e.occurred_at, "severity": e.severity,
            "summary": next((s["summary"] for s in e.sources if s.get("summary")), None),
        }

    return (
        "Morning situation report run. Changes since the last report: "
        + json.dumps(
            {
                "counts": changes.counts(),
                "escalated": [brief(e) for e in changes.escalated],
                "new": [brief(e) for e in changes.new],
                "updated": [brief(e) for e in changes.updated],
                "withdrawn": [d.get("title") or d["uid"] for d in changes.deleted],
            }
        )
        + "\nAll events (including unchanged) are ALREADY fetched and available to "
        "write_dashboard by uid — do NOT call fetch_feed. Assess the escalated and "
        "new events (what happened, where, how bad, who is affected; two sentences "
        "each at most), then call write_dashboard exactly once, referencing only "
        "the uids listed above."
    )


def _agent_loop(messages: list[dict], span_tracer, deadline: float,
                record: str | None = None) -> dict:
    """Returns run stats; enforces every cap in code."""
    turns = tokens = 0
    wrote = False
    cap = None
    try:
        # inside the guard: a missing key or client failure must reach the
        # fallback renderer, not crash the run (the report always exists)
        model = make_model(record=record)
    except Exception as exc:  # noqa: BLE001
        return {"turns": 0, "tokens": 0, "wrote": False, "cap_tripped": f"model_error: {exc}"}
    while turns < MAX_TURNS:
        if time.monotonic() > deadline:
            cap = "wall_clock"
            break
        with span_tracer.start_as_current_span("model_turn") as span:
            try:
                reply, usage = model.complete(messages, tools.SCHEMAS)
            except Exception as exc:  # noqa: BLE001 — model failure -> fallback path
                cap = f"model_error: {exc}"
                break
            span.set_attribute("tokens", usage.get("total_tokens") or 0)
        turns += 1
        # spend accounting: every request re-sends the whole conversation as
        # prompt, so summing per-request totals (or the chars/4 estimate of
        # the conversation) is deliberately cumulative-per-request
        tokens += usage.get("total_tokens") or (
            sum(len(str(m.get("content") or "")) for m in messages) // 4
        )
        messages.append(reply)
        if tokens > MAX_TOKENS:
            cap = "tokens"
            break
        calls = reply.get("tool_calls") or []
        if not calls:
            break
        for call in calls:
            name = call["function"]["name"]
            with span_tracer.start_as_current_span(f"tool:{name}"):
                result = tools.run(call)
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})
            if name == "write_dashboard":
                try:
                    wrote = wrote or json.loads(result).get("ok") is True
                except ValueError:
                    pass
        if wrote:
            break
    else:
        cap = "turns"
    if record and hasattr(model, "save"):
        model.save()
    return {"turns": turns, "tokens": tokens, "wrote": wrote, "cap_tripped": cap}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent.morning")
    parser.add_argument("--feeds", default=",".join(sorted(FEEDS)))
    parser.add_argument("--fixtures")
    parser.add_argument("--out", default="dashboard.html")
    parser.add_argument("--state", default=str(memory.STATE_PATH))
    parser.add_argument("--record", help="save the model transcript for replay")
    args = parser.parse_args(argv)
    os.environ["HADR_DASHBOARD_OUT"] = args.out

    t = tracer()
    started_at, t0 = _now(), time.monotonic()
    stats = {"turns": 0, "tokens": 0, "wrote": False, "cap_tripped": None}
    messages: list[dict] = []

    with t.start_as_current_span("morning_run") as root:
        with t.start_as_current_span("gather"):
            raw_events, statuses = gather(args.feeds.split(","), args.fixtures)
        events = dedupe.merge(raw_events)
        state = memory.load(args.state)
        changes = memory.diff(state, events)
        if not changes.quiet:
            state["last_change_at"] = _now()
        last_change = state.get("last_change_at")

        tools.reset()
        tools.seed(events, statuses, changes=changes, last_change_at=last_change)

        if changes.quiet:
            engine = "pipeline-quiet"
            render.write_dashboard(events, statuses, args.out, changes, last_change_at=last_change)
        else:
            messages = [
                {"role": "system", "content": SOUL.read_text()},
                {"role": "user", "content": _briefing(changes)},
            ]
            stats = _agent_loop(messages, t, deadline=t0 + MAX_SECONDS, record=args.record)
            html = Path(args.out).read_text() if Path(args.out).exists() else ""
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if stats["wrote"] and f"Data as of {today}" in html:
                engine = "agentic"
            else:
                engine = "fallback"
                render.write_dashboard(
                    events, statuses, args.out, changes, last_change_at=last_change,
                    notice="Automated assessment unavailable this run — deterministic "
                    "report only. See state/runs/ for the reason.",
                )
        root.set_attribute("engine", engine)

        memory.save(state, args.state)

    counts = changes.counts()
    record = {
        "started_at": started_at,
        "finished_at": _now(),
        "duration_ms": int((time.monotonic() - t0) * 1000),
        "feeds": [s.to_dict() for s in statuses],
        "significant_events": len(events),
        "changes": counts,
        "engine": engine,
        "model": os.environ.get("HADR_MODEL", "(default)"),
        "caps": {"turns": MAX_TURNS, "tokens": MAX_TOKENS, "seconds": MAX_SECONDS},
        **stats,
    }
    path = write_run(record, runs_dir=Path(args.state).parent / "runs")
    if messages:
        stamp = started_at.replace(":", "").replace("-", "")
        (path.parent / f"{stamp}-transcript.json").write_text(json.dumps(messages, indent=2))
    (Path(args.state).parent / "last_run.json").write_text(
        json.dumps({"finished_at": _now(), "changes": counts, "engine": engine}, indent=2)
    )
    print(f"engine={engine} events={len(events)} turns={stats['turns']} "
          f"tokens={stats['tokens']} cap={stats['cap_tripped']} -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
