#!/usr/bin/env python
"""Deterministic check: no recorded run exceeded its own caps — the checking
instrument for the spend/turn/time constraints (Goal.md: a constraint without
a checker will be ignored under pressure). Exit 0 on pass, 1 on fail.

    uv run python scripts/check_spend.py [state/runs]
"""

import json
import sys
from pathlib import Path


def main() -> int:
    runs_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "state/runs")
    records = sorted(runs_dir.glob("[0-9]*Z.json"))
    if not records:
        print("PASS - no run records yet")
        return 0
    failed = False
    for path in records:
        run = json.loads(path.read_text())
        caps = run.get("caps")
        if caps is None:
            continue  # pipeline-only run, nothing capped
        over = []
        if run.get("turns", 0) > caps["turns"]:
            over.append(f"turns {run['turns']}>{caps['turns']}")
        if run.get("tokens", 0) > caps["tokens"]:
            over.append(f"tokens {run['tokens']}>{caps['tokens']}")
        if run.get("duration_ms", 0) > caps["seconds"] * 1000 * 1.2:
            over.append(f"duration {run['duration_ms']}ms>{caps['seconds']}s")
        # a tripped cap that stopped the run IS enforcement working; the failure
        # mode is exceeding a cap with no trip recorded (enforcement broken)
        broken = bool(over) and not run.get("cap_tripped")
        status = "FAIL" if broken else "PASS"
        failed = failed or broken
        print(f"{status} - {path.name}: engine={run.get('engine')} "
              f"turns={run.get('turns')} tokens={run.get('tokens')} "
              f"cap_tripped={run.get('cap_tripped')}" + (f" over: {over}" if over else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
