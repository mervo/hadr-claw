from datetime import datetime, timezone

from hadr.events import Event, FeedStatus
from hadr.render import render


def _event(**overrides):
    base = dict(
        uid="usgs:test1",
        hazard="EQ",
        title="M 5.0 - somewhere",
        occurred_at="2026-07-08T01:00:00Z",
        updated_at="2026-07-08T01:10:00Z",
        lat=1.0,
        lon=103.0,
        severity={"mag": 5.0, "pager_alert": None, "sig": 400, "tsunami": 0},
        sources=[{"feed": "usgs", "id": "test1", "ids": ["test1"], "url": "https://x", "status": "automatic"}],
    )
    base.update(overrides)
    return Event(**base)


def _status(ok=True, **overrides):
    base = dict(feed="usgs", ok=ok, fetched_at="2026-07-08T01:20:00Z", latency_ms=100, event_count=1)
    base.update(overrides)
    return FeedStatus(**base)


def test_stamp_in_utc_and_sgt():
    html = render([_event()], [_status()], generated_at=datetime(2026, 7, 8, 0, 30, tzinfo=timezone.utc))
    assert "2026-07-08 00:30 UTC" in html
    assert "2026-07-08 08:30 SGT" in html  # SGT = UTC+8


def test_feed_derived_text_is_escaped():
    html = render([_event(title='<script>alert("x")</script>')], [_status()])
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_feed_failure_shows_banner_not_crash():
    html = render([], [_status(ok=False, error="boom", latency_ms=None, event_count=0)])
    assert "unreachable this run" in html
    assert "boom" in html


def test_empty_but_healthy_says_so():
    html = render([], [_status(event_count=0)])
    assert "No events pass the significance threshold" in html
