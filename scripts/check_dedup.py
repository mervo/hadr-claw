#!/usr/bin/env python
"""Deterministic check: cross-feed dedup merges the same physical event and
leaves unrelated events alone. Exit 0 on pass, 1 on fail.

    uv run python scripts/check_dedup.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from hadr import dedupe  # noqa: E402
from hadr.__main__ import gather  # noqa: E402


def main() -> int:
    events, statuses = gather(["usgs", "gdacs", "reliefweb"], "tests/fixtures/crossfeed")
    down = [s.feed for s in statuses if not s.ok]
    if down:
        print(f"FAIL: fixture feeds unreadable: {down}")
        return 1
    merged = dedupe.merge(events)
    checks = {
        "3 raw sources + 1 unrelated -> 2 events": len(events) == 4 and len(merged) == 2,
        "venezuela quake has all three feeds": sorted(
            s["feed"] for e in merged if e.glide for s in e.sources
        ) == ["gdacs", "reliefweb", "usgs"],
        "canonical uid is the GLIDE": any(e.uid == "glide:EQ-2026-000093-VEN" for e in merged),
        "unrelated quake untouched": any(len(e.sources) == 1 for e in merged),
    }
    for name, ok in checks.items():
        print(("PASS" if ok else "FAIL"), "-", name)
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
