"""Cross-feed dedup: the same physical event arrives from up to three feeds
under different identifiers. Match rules in priority order (each merge is
audited via `merged_by` on the absorbed source):

1. glide  — exact GLIDE number match (ties ReliefWeb to GDACS, days later)
2. alias  — any shared id across sources[].ids (e.g. NEIC id in both feeds)
3. spacetime — same hazard within 100 km and 30 min, magnitudes within 0.6
   (validated live: 18/19 GDACS quakes matched USGS this way)

A source joining an already-known cluster is an UPDATE, not a new event —
that distinction is Tier 3's job; here we only merge one run's snapshot.
"""

from __future__ import annotations

import math

from hadr.events import Event

MAX_KM = 100
MAX_SECONDS = 30 * 60
MAX_MAG_DELTA = 0.6

FEED_PRIORITY = {"gdacs": 0, "usgs": 1, "reliefweb": 2}


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    p = math.pi / 180
    a = (
        0.5
        - math.cos((lat2 - lat1) * p) / 2
        + math.cos(lat1 * p) * math.cos(lat2 * p) * (1 - math.cos((lon2 - lon1) * p)) / 2
    )
    return 12742 * math.asin(math.sqrt(a))


def _epoch(iso: str) -> float:
    from datetime import datetime

    return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() if iso else 0.0


def _match_rule(a: Event, b: Event) -> str | None:
    if a.glide and a.glide == b.glide:
        return "glide"
    a_ids = {i for s in a.sources for i in s["ids"]}
    b_ids = {i for s in b.sources for i in s["ids"]}
    if a_ids & b_ids:
        return "alias"
    if (
        a.hazard == b.hazard
        and None not in (a.lat, a.lon, b.lat, b.lon)
        and _haversine_km(a.lat, a.lon, b.lat, b.lon) <= MAX_KM
        and abs(_epoch(a.occurred_at) - _epoch(b.occurred_at)) <= MAX_SECONDS
    ):
        mag_a, mag_b = a.severity.get("mag"), b.severity.get("mag")
        if mag_a is None or mag_b is None or abs(mag_a - mag_b) <= MAX_MAG_DELTA:
            return "spacetime"
    return None


def _feed_rank(e: Event) -> int:
    return min(FEED_PRIORITY.get(s["feed"], 9) for s in e.sources)


def _absorb(primary: Event, other: Event, rule: str) -> None:
    known = {(s["feed"], s["id"]) for s in primary.sources}
    for src in other.sources:
        # re-fetching a feed must not stack duplicate source rows on the card
        if (src["feed"], src["id"]) not in known:
            primary.sources.append({**src, "merged_by": rule})
    for key, value in other.severity.items():
        if primary.severity.get(key) is None and value is not None:
            primary.severity[key] = value
    primary.glide = primary.glide or other.glide
    primary.country = primary.country or other.country
    primary.iso3 = primary.iso3 or other.iso3
    if primary.lat is None:
        primary.lat, primary.lon = other.lat, other.lon
    if primary.depth_km is None:
        primary.depth_km = other.depth_km
    primary.updated_at = max(primary.updated_at, other.updated_at)
    if primary.glide:
        primary.uid = f"glide:{primary.glide}"


def merge(events: list[Event]) -> list[Event]:
    """Greedy clustering — event counts are small (tens, not thousands)."""
    merged: list[Event] = []
    for event in sorted(events, key=_feed_rank):
        for existing in merged:
            rule = _match_rule(existing, event)
            if rule:
                _absorb(existing, event, rule)
                break
        else:
            if event.glide:
                event.uid = f"glide:{event.glide}"
            merged.append(event)
    return merged
