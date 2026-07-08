"""GDACS multi-hazard event list (see feeds/gdacs.md).

Datetimes in this feed are naive strings; they are UTC — verified by matching
18/19 live GDACS earthquakes to USGS epoch timestamps within a second.
"""

from __future__ import annotations

import json
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


def is_significant(props: dict) -> bool:
    if props.get("alertlevel") in KEEP_ALERTS:
        return True
    if props.get("eventtype") == "EQ":
        severity = (props.get("severitydata") or {}).get("severity") or 0
        return severity >= MIN_EQ_MAG
    return False


def normalize(raw: dict) -> list[Event]:
    events = []
    for feature in raw.get("features", []):
        props = feature["properties"]
        if props.get("iscurrent") != "true" or not is_significant(props):
            continue
        lon, lat = feature["geometry"]["coordinates"][:2]
        severity_data = props.get("severitydata") or {}
        events.append(
            Event(
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
                    "mag": severity_data.get("severity") if props.get("eventtype") == "EQ" else None,
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
        )
    return events
