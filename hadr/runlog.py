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
    # prune each file family separately so transcripts don't crowd out records
    for pattern in ("[0-9]*Z.json", "*-transcript.json"):
        for old in sorted(runs.glob(pattern))[:-KEEP]:
            old.unlink()
    return path
