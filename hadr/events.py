"""Unified event schema. Feeds normalize into Event at the feed boundary;
everything downstream (dedup, memory, render, the agent's tools) speaks Event."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Event:
    uid: str                # canonical id, e.g. "usgs:ci41287863"; GLIDE once merged (Tier 2)
    hazard: str             # GDACS codes: EQ/TC/FL/VO/DR/WF
    title: str
    occurred_at: str        # ISO8601 UTC
    updated_at: str         # ISO8601 UTC
    lat: float | None       # ReliefWeb entries carry no coordinates
    lon: float | None
    depth_km: float | None = None
    country: str | None = None
    iso3: str | None = None
    severity: dict[str, Any] = field(default_factory=dict)
    glide: str | None = None
    sources: list[dict[str, Any]] = field(default_factory=list)
    status: str = "active"

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class FeedStatus:
    feed: str
    ok: bool
    fetched_at: str         # ISO8601 UTC
    latency_ms: int | None = None
    error: str | None = None
    event_count: int = 0    # events surviving the noise filter

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)
