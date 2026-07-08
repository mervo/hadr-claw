"""The claw's tools: bounded actions the loop runs on the model's behalf.
Thin wrappers over the deterministic pipeline in hadr/ — the model never sees
raw feeds, only normalized, noise-filtered, size-capped events (a raw USGS
payload is 1–2 MB; two of those and an open model's context is gone).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from hadr import dedupe, render
from hadr.__main__ import FEEDS, gather
from hadr.events import Event, FeedStatus

MAX_EVENTS = 50
MAX_ASSESSMENT_CHARS = 1200
MAX_HEADLINE_CHARS = 200
MAX_OVERVIEW_CHARS = 2000

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
    {
        "type": "function",
        "function": {
            "name": "write_dashboard",
            "description": (
                "Write the HTML situation report. Assessments must reference events "
                "by the exact uid returned by fetch_feed — unknown uids are rejected. "
                "Event facts (magnitude, place, links) are injected from feed data; "
                "you supply only the analytical prose."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "headline": {"type": "string", "description": "one-line situation headline"},
                    "overview": {"type": "string", "description": "2-4 sentence overview"},
                    "assessments": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "uid": {"type": "string"},
                                "assessment": {
                                    "type": "string",
                                    "description": "what happened, where, how bad, who is affected",
                                },
                                "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                            },
                            "required": ["uid", "assessment", "priority"],
                        },
                    },
                },
                "required": ["headline", "overview", "assessments"],
            },
        },
    },
]

# events the model has actually fetched this session, by uid — write_dashboard
# may only reference these (the model cannot invent events)
_fetched: dict[str, Event] = {}
_statuses: dict[str, FeedStatus] = {}
_context: dict = {}  # changes/last_change_at set by agent.morning for section rendering


def fetched_events() -> dict[str, Event]:
    return _fetched


def reset() -> None:
    """Fresh session state (tests, and one production run per process)."""
    _fetched.clear()
    _statuses.clear()
    _context.clear()


def seed(events: list[Event], statuses: list[FeedStatus], **context) -> None:
    """agent.morning pre-fetches deterministically and injects the results;
    the model doesn't have to re-fetch (but may)."""
    _fetched.update({e.uid: e for e in events})
    _statuses.update({s.feed: s for s in statuses})
    _context.update(context)


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


def write_dashboard(headline: str, overview: str, assessments: list[dict]) -> str:
    unknown = [a["uid"] for a in assessments if a["uid"] not in _fetched]
    if unknown:
        return json.dumps(
            {
                "ok": False,
                "error": f"unknown uids {unknown}; valid uids are exactly those returned "
                "by fetch_feed this session",
                "valid_uids": sorted(_fetched),
            }
        )
    if not _fetched:
        return json.dumps({"ok": False, "error": "fetch at least one feed first"})
    assessed = {
        a["uid"]: {
            "assessment": a["assessment"][:MAX_ASSESSMENT_CHARS],
            "priority": a.get("priority", "medium"),
        }
        for a in assessments
    }
    out = Path(os.environ.get("HADR_DASHBOARD_OUT", "dashboard.html"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        render.render(
            list(_fetched.values()),
            list(_statuses.values()),
            changes=_context.get("changes"),
            last_change_at=_context.get("last_change_at"),
            headline=headline[:MAX_HEADLINE_CHARS],
            overview=overview[:MAX_OVERVIEW_CHARS],
            assessments=assessed,
        )
    )
    return json.dumps({"ok": True, "path": str(out), "events": len(_fetched),
                       "assessed": len(assessed)})


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


_HANDLERS = {"fetch_feed": fetch_feed, "write_dashboard": write_dashboard}
