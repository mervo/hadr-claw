#!/usr/bin/env python
"""Run every deterministic checker; one line per checker, exit nonzero if any
fail. This is the instrument the overnight goal (goal.md) is checked against.

Child checkers get PYTHONPATH=<cwd> so pristine copies executed from a temp
dir still import the repo's hadr/ package.

    uv run python scripts/run_checkers.py [--dashboard PATH] [--state PATH]
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard", default="dashboard.html")
    parser.add_argument("--state", default="state/seen_events.json")
    args = parser.parse_args()

    env = {**os.environ, "PYTHONPATH": str(Path.cwd())}
    checkers: dict[str, list[str]] = {
        "check_schema.py": [],
        "check_dedup.py": [],
        "check_memory.py": [],
        "check_dashboard.py": [args.dashboard, args.state],
        "check_freshness.py": [args.dashboard],
        "check_spend.py": [],
    }
    failed = []
    for name, extra in checkers.items():
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / name), *extra],
            capture_output=True, text=True, env=env,
        )
        status = "PASS" if result.returncode == 0 else "FAIL"
        if result.returncode != 0:
            failed.append(name)
        detail = (result.stdout or result.stderr).strip().splitlines()
        print(f"{status} {name}" + (f" :: {detail[-1]}" if detail else ""))
        if result.returncode != 0:
            for line in detail:
                print(f"       {line}")
    print(f"\n{len(checkers) - len(failed)}/{len(checkers)} checkers green")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
