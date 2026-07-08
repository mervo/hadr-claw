"""GDACS multi-hazard event list (see feeds/gdacs.md).

Datetimes in this feed are naive strings; they are UTC — verified by matching
18/19 live GDACS earthquakes to USGS epoch timestamps within a second.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import httpx

from hadr import USER_AGENT
from hadr.events import Event

URL = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/EVENTS4APP"
FIXTURE_NAME = "events.json"
WINDOW_HOURS = None  # not a rolling window: events stay while GDACS marks them current

# Reporting alert level is the event-level `alertlevel`; episode-level values
# thrash on long-running events (feeds/gdacs.md Q1)
KEEP_ALERTS = {"Orange", "Red"}
MIN_EQ_MAG = 4.5  # Green earthquakes only clear the same bar as USGS quakes

log = logging.getLogger(__name__)


def fetch_raw() -> dict:
    with httpx.Client(
        follow_redirects=True, timeout=30, headers={"User-Agent": USER_AGENT}
    ) as client:
        resp = client.get(URL)
        resp.raise_for_status()
        return resp.json()


def load_fixture(path: str | Path) -> dict:
    with open(path) as f:
        return json.load(f)


def _iso(naive: str) -> str:
    return naive.split(".")[0] + "Z"


def _num(value) -> float | None:
    """severitydata.severity has been observed as both number and string."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def is_significant(props: dict) -> bool:
    if props.get("alertlevel") in KEEP_ALERTS:
        return True
    if props.get("eventtype") == "EQ":
        severity = _num((props.get("severitydata") or {}).get("severity")) or 0
        return severity >= MIN_EQ_MAG
    return False


def normalize(raw: dict) -> list[Event]:
    """One malformed feature (null geometry, missing fromdate) skips that
    feature, never the feed — a crash here would report zero events all run."""
    events = []
    for feature in raw.get("features", []):
        try:
            event = _normalize_one(feature)
        except (KeyError, TypeError, ValueError, IndexError, AttributeError) as exc:
            log.warning("gdacs: skipping malformed feature %r: %s",
                        ((feature or {}).get("properties") or {}).get("eventid"), exc)
            continue
        if event:
            events.append(event)
    return events


def _normalize_one(feature: dict) -> Event | None:
    props = feature["properties"]
    # iscurrent is the string "true" today, but tolerate a boolean — a silent
    # type change upstream must not drop every event on the floor
    if str(props.get("iscurrent")).lower() != "true" or not is_significant(props):
        return None
    lon, lat = feature["geometry"]["coordinates"][:2]
    severity_data = props.get("severitydata") or {}
    return Event(
        uid=f"gdacs:{props['eventid']}",
        hazard=props.get("eventtype") or "OT",
        title=props.get("name") or props.get("eventname") or "",
        occurred_at=_iso(props["fromdate"]),
        updated_at=_iso(props.get("datemodified") or props["fromdate"]),
        lat=lat,
        lon=lon,
        country=props.get("country") or None,
        iso3=props.get("iso3") or None,
        severity={
            "gdacs_alert": props.get("alertlevel"),
            "alertscore": props.get("alertscore"),
            "mag": _num(severity_data.get("severity")) if props.get("eventtype") == "EQ" else None,
            "text": severity_data.get("severitytext"),
        },
        glide=props.get("glide") or None,
        sources=[
            {
                "feed": "gdacs",
                "id": str(props["eventid"]),
                "ids": [str(props["eventid"])],
                "url": (props.get("url") or {}).get("report"),
                "episode_id": props.get("episodeid"),
                "episode_alert": props.get("episodealertlevel"),
                "source": props.get("source"),
            }
        ],
    )
