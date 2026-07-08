"""CLI: fetch feeds, normalize, render the dashboard, record the run.

    uv run python -m hadr --feeds usgs [--fixtures tests/fixtures] [--out dashboard.html]
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from hadr import dedupe, memory
from hadr.events import Event, FeedStatus
from hadr.feeds import gdacs, reliefweb, usgs
from hadr.render import write_dashboard
from hadr.runlog import write_run

FEEDS = {"usgs": usgs, "gdacs": gdacs, "reliefweb": reliefweb}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def gather(names: list[str], fixtures: str | None) -> tuple[list[Event], list[FeedStatus]]:
    """Fetch + normalize each feed in isolation: one feed failing must not
    take down the report (it shows as a banner instead)."""
    events: list[Event] = []
    statuses: list[FeedStatus] = []
    for name in names:
        mod = FEEDS[name]
        started = time.monotonic()
        try:
            if fixtures:
                raw = mod.load_fixture(Path(fixtures) / name / mod.FIXTURE_NAME)
            else:
                raw = mod.fetch_raw()
            found = mod.normalize(raw)
            events.extend(found)
            statuses.append(
                FeedStatus(
                    feed=name, ok=True, fetched_at=_now(),
                    latency_ms=int((time.monotonic() - started) * 1000),
                    event_count=len(found),
                )
            )
        except Exception as exc:  # noqa: BLE001 — isolation boundary
            statuses.append(FeedStatus(feed=name, ok=False, fetched_at=_now(), error=str(exc)))
    return events, statuses


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hadr")
    parser.add_argument(
        "--feeds", default="usgs,gdacs,reliefweb", help="comma-separated: " + ",".join(FEEDS)
    )
    parser.add_argument("--fixtures", help="read feed payloads from this dir instead of the network")
    parser.add_argument("--out", default="dashboard.html")
    parser.add_argument("--state", default=str(memory.STATE_PATH), help="seen-events state file")
    args = parser.parse_args(argv)

    names = [n.strip() for n in args.feeds.split(",") if n.strip()]
    unknown = [n for n in names if n not in FEEDS]
    if unknown:
        parser.error(f"unknown feed(s) {unknown}; available: {sorted(FEEDS)}")

    started_at = _now()
    t0 = time.monotonic()
    raw_events, statuses = gather(names, args.fixtures)
    events = dedupe.merge(raw_events)

    state = memory.load(args.state)
    changes = memory.diff(state, events)
    if not changes.quiet:
        state["last_change_at"] = _now()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_dashboard(events, statuses, out, changes=changes,
                    last_change_at=state.get("last_change_at"))
    memory.save(state, args.state)

    counts = changes.counts()
    write_run(
        {
            "started_at": started_at,
            "finished_at": _now(),
            "duration_ms": int((time.monotonic() - t0) * 1000),
            "feeds": [s.to_dict() for s in statuses],
            "significant_events": len(events),
            "merged_away": len(raw_events) - len(events),
            "changes": counts,
            "engine": "pipeline",
        }
    )
    Path(args.state).parent.mkdir(parents=True, exist_ok=True)
    (Path(args.state).parent / "last_run.json").write_text(
        json.dumps({"finished_at": _now(), "changes": counts}, indent=2)
    )
    print(
        f"{len(events)} significant event(s) from "
        f"{sum(s.ok for s in statuses)}/{len(statuses)} feed(s) -> {out} | "
        + (", ".join(f"{v} {k}" for k, v in counts.items() if k != "unchanged" and v)
           or "no changes")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
