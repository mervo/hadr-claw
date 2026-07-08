#!/usr/bin/env python
"""Deterministic check: the dashboard's freshness stamp exists and is recent —
quiet is a statement, not an absence; a stale page is a dead claw.
Exit 0 on pass, 1 on fail.

    uv run python scripts/check_freshness.py [dashboard.html]
    HADR_FRESH_MAX_HOURS=26 by default
"""

import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    dash = Path(sys.argv[1] if len(sys.argv) > 1 else "dashboard.html")
    max_hours = float(os.environ.get("HADR_FRESH_MAX_HOURS", "26"))
    if not dash.exists():
        print(f"FAIL - {dash} does not exist")
        return 1
    stamp = re.search(r"Data as of (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) UTC", dash.read_text())
    if not stamp:
        print("FAIL - no freshness stamp")
        return 1
    written = datetime.strptime(stamp.group(1), "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    age_hours = (datetime.now(timezone.utc) - written).total_seconds() / 3600
    ok = age_hours <= max_hours
    print(f"{'PASS' if ok else 'FAIL'} - stamp {stamp.group(1)} UTC is "
          f"{age_hours:.1f}h old (max {max_hours}h)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
