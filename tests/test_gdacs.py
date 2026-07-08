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


def _feature(**props):
    base = {
        "eventid": 999001, "eventtype": "TC", "alertlevel": "Red",
        "iscurrent": "true", "fromdate": "2026-07-01T00:00:00",
        "datemodified": "2026-07-08T03:20:05", "name": "TC TEST-26",
    }
    base.update(props)
    return {"geometry": {"type": "Point", "coordinates": [134.1, 16.9]},
            "properties": base}


def test_malformed_feature_skipped_not_fatal():
    """A single bad feature (null geometry, null fromdate) must never take
    the whole feed down to zero events."""
    good = _feature(eventid=999001)
    null_geometry = _feature(eventid=999002)
    null_geometry["geometry"] = None
    null_fromdate = _feature(eventid=999003, fromdate=None)
    events = gdacs.normalize({"features": [null_geometry, good, null_fromdate]})
    assert [e.uid for e in events] == ["gdacs:999001"]


def test_boolean_iscurrent_and_string_severity_tolerated():
    """iscurrent is the string 'true' today; a silent upstream type change to
    boolean must not drop every event. String magnitudes coerce to float."""
    quake = _feature(
        eventid=999004, eventtype="EQ", alertlevel="Green", iscurrent=True,
        severitydata={"severity": "6.2", "severitytext": "Magnitude 6.2M"},
    )
    events = gdacs.normalize({"features": [quake]})
    assert len(events) == 1
    assert events[0].severity["mag"] == 6.2


def test_event_level_alert_is_reported_and_episode_kept_aside():
    events = gdacs.normalize(gdacs.load_fixture(FIXTURE))
    e = events[0]
    assert e.severity["gdacs_alert"] in ("Green", "Orange", "Red")
    assert "episode_alert" in e.sources[0]
