"""The claw's tools: bounded actions the loop runs on the model's behalf.
Thin wrappers over the deterministic pipeline in hadr/ — the model never sees
raw feeds, only normalized, noise-filtered, size-capped events (a raw USGS
payload is 1–2 MB; two of those and an open model's context is gone).
"""

from __future__ import annotations

import json
import os

from hadr import dedupe
from hadr.__main__ import FEEDS, gather
from hadr.events import Event, FeedStatus

MAX_EVENTS = 50

SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "fetch_feed",
            "description": (
                "Fetch a disaster feed and return normalized significant events. "
                "Returns JSON: {feed_ok, events: [{uid, hazard, title, occurred_at, "
                "lat, lon, country, severity, sources}]}"
            ),
            "parameters": {
                "type": "object",
                "properties": {"feed": {"type": "string", "enum": sorted(FEEDS)}},
                "required": ["feed"],
            },
        },
    },
]

# events the model has actually fetched this session, by uid — write_dashboard
# may only reference these (the model cannot invent events)
_fetched: dict[str, Event] = {}
_statuses: dict[str, FeedStatus] = {}


def fetched_events() -> dict[str, Event]:
    return _fetched


def fetch_feed(feed: str) -> str:
    events, (status,) = gather([feed], os.environ.get("HADR_FIXTURES") or None)
    merged = dedupe.merge(list(_fetched.values()) + events)
    _fetched.clear()
    _fetched.update({e.uid: e for e in merged})
    _statuses[feed] = status
    if not status.ok:
        return json.dumps({"feed_ok": False, "error": status.error})
    listed = sorted(_fetched.values(), key=lambda e: e.occurred_at, reverse=True)[:MAX_EVENTS]
    payload = {
        "feed_ok": True,
        "truncated_to": MAX_EVENTS if len(_fetched) > MAX_EVENTS else None,
        "events": [e.to_dict() for e in listed],
    }
    return json.dumps(payload)


def run(tool_call: dict) -> str:
    """Dispatch one tool call; errors go back to the model as the result."""
    name = tool_call["function"]["name"]
    try:
        arguments = json.loads(tool_call["function"]["arguments"] or "{}")
    except json.JSONDecodeError as exc:
        return f"error: tool arguments were not valid JSON ({exc}); retry once with valid JSON"
    handler = _HANDLERS.get(name)
    if handler is None:
        return f"error: unknown tool {name!r}"
    try:
        return handler(**arguments)
    except TypeError as exc:
        return f"error: bad arguments for {name}: {exc}"
    except Exception as exc:  # noqa: BLE001 — the model gets one chance to react
        return f"error: {name} failed: {exc}"


_HANDLERS = {"fetch_feed": fetch_feed}
