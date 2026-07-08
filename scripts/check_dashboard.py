#!/usr/bin/env python
"""Deterministic check: the published dashboard is fresh, safe, and consistent
with memory. Exit 0 on pass, 1 on fail.

    uv run python scripts/check_dashboard.py [dashboard.html] [state/seen_events.json]
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    dash = Path(sys.argv[1] if len(sys.argv) > 1 else "dashboard.html")
    state_path = Path(sys.argv[2] if len(sys.argv) > 2 else "state/seen_events.json")
    if not dash.exists():
        print(f"FAIL - {dash} does not exist")
        return 1
    html = dash.read_text()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    active_titles = []
    if state_path.exists():
        state = json.loads(state_path.read_text())
        active_titles = [
            e.get("title", "") for e in state["events"].values() if e.get("status") == "active"
        ]

    stamp = re.search(r"Data as of (\d{4}-\d{2}-\d{2})", html)
    checks = {
        "freshness stamp present": bool(stamp),
        "stamp is today (UTC)": bool(stamp) and stamp.group(1) == today,
        "no script tags (feed text escaped)": "<script" not in html.lower(),
        "ops strip present": 'class="ops"' in html,
        "active events appear on the page": not active_titles
        or sum(1 for t in active_titles if t and t[:40] in html) >= len(active_titles) * 0.9,
    }
    for name, ok in checks.items():
        print(("PASS" if ok else "FAIL"), "-", name)
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
