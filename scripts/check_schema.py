#!/usr/bin/env python
"""Deterministic check: every feed normalizer produces valid unified Events
from its fixture. Exit 0 on pass, 1 on fail.

    uv run python scripts/check_schema.py
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))  # repo root — survives running a copied checker

from hadr import dedupe  # noqa: E402
from hadr.__main__ import gather  # noqa: E402

ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
# GDACS event types + official GLIDE hazard codes (ReliefWeb uids inherit these)
HAZARDS = {
    "EQ", "TC", "FL", "VO", "DR", "WF", "OT",  # GDACS
    "AC", "AV", "CE", "CW", "EC", "EP", "ET", "FA", "FF", "FR", "HT", "IN",
    "LS", "MS", "SL", "SS", "ST", "TO", "TS", "VW", "WV",  # GLIDE
}


def problems(e) -> list[str]:
    out = []
    if not e.uid or ":" not in e.uid:
        out.append(f"bad uid {e.uid!r}")
    if not e.title:
        out.append("empty title")
    if e.hazard not in HAZARDS:
        out.append(f"unknown hazard {e.hazard!r}")
    if not ISO.match(e.occurred_at or ""):
        out.append(f"bad occurred_at {e.occurred_at!r}")
    if not ISO.match(e.updated_at or ""):
        out.append(f"bad updated_at {e.updated_at!r}")
    if (e.lat is None) != (e.lon is None):
        out.append("half a coordinate")
    if e.lat is not None and not (-90 <= e.lat <= 90 and -180 <= e.lon <= 180):
        out.append(f"coords out of range ({e.lat}, {e.lon})")
    if not e.sources or any(not s.get("feed") or "ids" not in s for s in e.sources):
        out.append("sources missing feed/ids")
    if e.glide and not re.fullmatch(r"[A-Z0-9]{2}-\d{4}-\d{6}-[A-Z]{3}", e.glide):
        out.append(f"malformed glide {e.glide!r}")
    return out


def main() -> int:
    events, statuses = gather(["usgs", "gdacs", "reliefweb"], "tests/fixtures")
    down = [s.feed for s in statuses if not s.ok]
    if down:
        print(f"FAIL - fixtures unreadable: {down}")
        return 1
    merged = dedupe.merge(events)
    bad = [(e.uid, p) for e in merged for p in problems(e)]
    for uid, p in bad:
        print(f"FAIL - {uid}: {p}")
    print(f"{'FAIL' if bad else 'PASS'} - {len(merged)} events validated "
          f"({len(events)} raw), {len(bad)} problem(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
