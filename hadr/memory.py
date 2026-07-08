"""The claw's memory: which events it has already seen, and what changed.

State lives in state/seen_events.json (committed — on GitHub Actions the runner
is wiped, so memory only survives via the repo). Each run diffs fresh events
against the state and classifies:

  NEW        uid (or any source-id alias) never seen before
  ESCALATED  alert level rose (Green<Orange<Red / PAGER green<yellow<orange<red)
  UPDATED    fingerprint changed (magnitude revision, new source joining, …)
  DELETED    gone from its feed while still inside that feed's rolling window
  aged_out   gone, but old enough that the window rolled past it — silent
  UNCHANGED  fingerprint identical

Fingerprints round lat/lon to 2 dp and magnitude to 1 dp: USGS revises
locations by metres constantly, and without rounding every run screams UPDATED.

Events are matched to state by uid first, then by any shared source id — a
cluster's canonical uid can change when a GLIDE arrives late, and that must
read as the same event, not a deletion plus a birth.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from hadr.events import Event

STATE_PATH = Path("state/seen_events.json")

_ALERT_RANKS = {"green": 0, "yellow": 1, "orange": 2, "red": 3}
# only USGS is a rolling window; GDACS/ReliefWeb entries just age out of scope
_FEED_WINDOW_HOURS = {"usgs": 24}
# non-active entries older than this are dropped from state — the committed
# memory file must not grow unbounded over a daily heartbeat
PRUNE_AFTER_DAYS = 30


def alert_rank(event: Event) -> int:
    levels = [event.severity.get("gdacs_alert"), event.severity.get("pager_alert")]
    return max((_ALERT_RANKS.get(str(lv).lower(), -1) for lv in levels), default=-1)


def alert_label(event: Event) -> str | None:
    # must agree with alert_rank: recording the lower of two levels would make
    # the next run read "escalated" forever (e.g. GDACS Green + PAGER orange)
    levels = [lv for lv in (event.severity.get("gdacs_alert"), event.severity.get("pager_alert")) if lv]
    return max(levels, key=lambda lv: _ALERT_RANKS.get(str(lv).lower(), -1), default=None)


def fingerprint(event: Event) -> str:
    salient = {
        "hazard": event.hazard,
        "title": event.title,
        "lat": round(event.lat, 2) if event.lat is not None else None,
        "lon": round(event.lon, 2) if event.lon is not None else None,
        "mag": round(m, 1) if (m := event.severity.get("mag")) is not None else None,
        "alert": alert_rank(event),
        "feeds": sorted({s["feed"] for s in event.sources}),
        "statuses": sorted(str(s.get("status")) for s in event.sources),
        "summary": next((s["summary"] for s in event.sources if s.get("summary")), None),
    }
    return "sha256:" + hashlib.sha256(json.dumps(salient, sort_keys=True).encode()).hexdigest()


def _aliases(event: Event) -> list[str]:
    ids = {event.uid}
    for s in event.sources:
        ids.add(f"{s['feed']}:{s['id']}")
        ids.update(s["ids"])
    return sorted(ids)


@dataclass
class Changes:
    new: list[Event] = field(default_factory=list)
    escalated: list[Event] = field(default_factory=list)
    updated: list[Event] = field(default_factory=list)
    unchanged: list[Event] = field(default_factory=list)
    deleted: list[dict] = field(default_factory=list)  # state entries, not Events

    def counts(self) -> dict[str, int]:
        return {
            "new": len(self.new),
            "escalated": len(self.escalated),
            "updated": len(self.updated),
            "unchanged": len(self.unchanged),
            "deleted": len(self.deleted),
        }

    @property
    def quiet(self) -> bool:
        return not (self.new or self.escalated or self.updated or self.deleted)


def load(path: str | Path = STATE_PATH) -> dict:
    path = Path(path)
    if not path.exists():
        return {"version": 1, "updated_at": None, "events": {}}
    return json.loads(path.read_text())


def save(state: dict, path: str | Path = STATE_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True))


def _inside_window(entry: dict, now: datetime) -> bool:
    for feed in entry.get("feeds", []):
        hours = _FEED_WINDOW_HOURS.get(feed)
        if hours and entry.get("occurred_at"):
            occurred = datetime.fromisoformat(entry["occurred_at"].replace("Z", "+00:00"))
            if (now - occurred).total_seconds() < hours * 3600:
                return True
    return False


def diff(state: dict, events: list[Event], now: datetime | None = None) -> Changes:
    """Classify events against state and update state in place."""
    now = now or datetime.now(timezone.utc)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    alias_index = {
        alias: uid for uid, entry in state["events"].items() for alias in entry.get("aliases", [uid])
    }

    changes = Changes()
    seen_uids = set()
    for event in events:
        fp = fingerprint(event)
        old_uid = alias_index.get(event.uid) or next(
            (alias_index[a] for a in _aliases(event) if a in alias_index), None
        )
        entry = state["events"].pop(old_uid, None) if old_uid else None
        if entry is None:
            changes.new.append(event)
            entry = {
                "first_seen": now_iso,
                "occurred_at": event.occurred_at,
                "alert_history": [[now_iso, alert_label(event)]],
            }
        else:
            # compare to the most recent recorded level, not the all-time max:
            # a re-escalation after a dip must surface on the watch floor again
            last_rank = _ALERT_RANKS.get(str(entry["alert_history"][-1][1]).lower(), -1)
            if alert_rank(event) != last_rank:
                entry["alert_history"].append([now_iso, alert_label(event)])
            if alert_rank(event) > last_rank:
                changes.escalated.append(event)
            elif entry["fingerprint"] != fp:
                changes.updated.append(event)
            else:
                changes.unchanged.append(event)

        entry.update(
            {
                "last_seen": now_iso,
                "fingerprint": fp,
                "aliases": _aliases(event),
                "feeds": sorted({s["feed"] for s in event.sources}),
                "status": "active",
                "title": event.title,
            }
        )
        state["events"][event.uid] = entry
        seen_uids.add(event.uid)

    for uid, entry in state["events"].items():
        if uid in seen_uids or entry.get("status") != "active":
            continue
        if _inside_window(entry, now):
            entry["status"] = "deleted"
            changes.deleted.append({"uid": uid, **entry})
        else:
            entry["status"] = "aged_out"

    # prune: non-active entries unseen for PRUNE_AFTER_DAYS drop out entirely,
    # so the committed file stays bounded over a daily heartbeat
    cutoff = now.timestamp() - PRUNE_AFTER_DAYS * 86400
    for uid in [
        uid
        for uid, entry in state["events"].items()
        if entry.get("status") != "active"
        and datetime.fromisoformat(entry["last_seen"].replace("Z", "+00:00")).timestamp() < cutoff
    ]:
        del state["events"][uid]

    state["updated_at"] = now_iso
    return changes
