"""USGS real-time earthquake feed (see feeds/usgs.md)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import httpx

from hadr import USER_AGENT
from hadr.events import Event

URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"
FIXTURE_NAME = "all_day.geojson"
WINDOW_HOURS = 24  # all_day is a rolling window; memory (Tier 3) needs this to
                   # distinguish deletions from normal aging-out

# Noise filter for a global watch floor (thresholds documented in CLAUDE.md)
MIN_MAG = 4.5
MIN_SIG = 600

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


def is_significant(props: dict) -> bool:
    return bool(
        (props.get("mag") or 0) >= MIN_MAG
        or (props.get("sig") or 0) >= MIN_SIG
        or props.get("alert")
    )


def _iso(epoch_ms: int) -> str:
    return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize(raw: dict) -> list[Event]:
    """One malformed feature (null geometry, missing time) skips that feature,
    never the feed — a crash here would report zero events for the whole run."""
    events = []
    for feature in raw.get("features", []):
        try:
            event = _normalize_one(feature)
        except (KeyError, TypeError, ValueError, IndexError, AttributeError) as exc:
            log.warning("usgs: skipping malformed feature %r: %s",
                        (feature or {}).get("id"), exc)
            continue
        if event:
            events.append(event)
    return events


def _normalize_one(feature: dict) -> Event | None:
    props = feature["properties"]
    if props.get("type") != "earthquake" or not is_significant(props):
        return None
    lon, lat, *rest = feature["geometry"]["coordinates"]
    # `ids` is a comma-wrapped list: one id per reporting network for the same
    # quake. All are kept as aliases so Tier 2 can match records across feeds.
    ids = [i for i in (props.get("ids") or "").split(",") if i]
    return Event(
        uid=f"usgs:{feature['id']}",
        hazard="EQ",
        title=props.get("title") or "",
        occurred_at=_iso(props["time"]),
        updated_at=_iso(props.get("updated") or props["time"]),
        lat=lat,
        lon=lon,
        depth_km=rest[0] if rest else None,
        severity={
            "mag": props.get("mag"),
            "pager_alert": props.get("alert"),
            "sig": props.get("sig"),
            "tsunami": props.get("tsunami"),
        },
        sources=[
            {
                "feed": "usgs",
                "id": feature["id"],
                "ids": ids,
                "url": props.get("url"),
                "status": props.get("status"),
            }
        ],
    )
