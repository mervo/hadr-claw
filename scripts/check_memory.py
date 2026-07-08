#!/usr/bin/env python
"""Deterministic check: memory classifies day1->day2 changes correctly —
escalation, revision, new, deletion-inside-window vs silent age-out.
Exit 0 on pass, 1 on fail.

    uv run python scripts/check_memory.py
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from hadr import dedupe, memory  # noqa: E402
from hadr.__main__ import gather  # noqa: E402

NOW = datetime(2026, 7, 8, 0, 0, tzinfo=timezone.utc)


def _events(day):
    events, _ = gather(["usgs", "gdacs"], f"tests/fixtures/{day}")
    return dedupe.merge(events)


def main() -> int:
    state = memory.load("/nonexistent")
    day1 = memory.diff(state, _events("day1"), now=NOW)
    rerun = memory.diff(state, _events("day1"), now=NOW)
    day2 = memory.diff(state, _events("day2"), now=NOW)

    checks = {
        "first sight -> 5 new": day1.counts()["new"] == 5,
        "identical rerun is quiet": rerun.quiet,
        "alert rise -> escalated": [e.title for e in day2.escalated] == ["Earthquake in Malaysia"],
        "mag revision -> updated": [e.uid for e in day2.updated] == ["usgs:usday0005"],
        "fresh quake -> new": [e.uid for e in day2.new] == ["usgs:usday0004"],
        "gone inside window -> deleted": [d["uid"] for d in day2.deleted] == ["usgs:usday0003"],
        "window rolled past -> aged out, silent": (
            state["events"]["usgs:usday0002"]["status"] == "aged_out"
        ),
    }
    for name, ok in checks.items():
        print(("PASS" if ok else "FAIL"), "-", name)
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
