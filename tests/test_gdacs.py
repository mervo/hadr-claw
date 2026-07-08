from pathlib import Path

from hadr.feeds import gdacs

FIXTURE = Path(__file__).parent / "fixtures" / "gdacs" / "events.json"


def test_normalize_keeps_orange_red_and_significant_quakes_only():
    events = gdacs.normalize(gdacs.load_fixture(FIXTURE))
    for e in events:
        assert (
            e.severity["gdacs_alert"] in gdacs.KEEP_ALERTS
            or (e.hazard == "EQ" and (e.severity["mag"] or 0) >= gdacs.MIN_EQ_MAG)
        )
    # fixture contains 5 Green wildfires that must all be dropped
    assert not any(e.hazard == "WF" and e.severity["gdacs_alert"] == "Green" for e in events)
    assert any(e.severity["gdacs_alert"] in ("Orange", "Red") for e in events)


def test_naive_datetimes_become_utc_iso():
    events = gdacs.normalize(gdacs.load_fixture(FIXTURE))
    for e in events:
        assert e.occurred_at.endswith("Z") and "T" in e.occurred_at
        assert e.updated_at.endswith("Z")


def test_event_level_alert_is_reported_and_episode_kept_aside():
    events = gdacs.normalize(gdacs.load_fixture(FIXTURE))
    e = events[0]
    assert e.severity["gdacs_alert"] in ("Green", "Orange", "Red")
    assert "episode_alert" in e.sources[0]
