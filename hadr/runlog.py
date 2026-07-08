"""Run records: one JSON file per run under state/runs/, pruned to the newest 14.
The observability base layer — the ops panel and check_spend.py read these."""

from __future__ import annotations

import json
from pathlib import Path

KEEP = 14


def write_run(record: dict, runs_dir: str | Path = "state/runs") -> Path:
    runs = Path(runs_dir)
    runs.mkdir(parents=True, exist_ok=True)
    stamp = record["started_at"].replace(":", "").replace("-", "")
    path = runs / f"{stamp}.json"
    path.write_text(json.dumps(record, indent=2))
    for old in sorted(runs.glob("*.json"))[:-KEEP]:
        old.unlink()
    return path
