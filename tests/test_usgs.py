from pathlib import Path

from hadr.feeds import usgs

FIXTURE = Path(__file__).parent / "fixtures" / "usgs" / "all_day.geojson"


def test_normalize_filters_noise_and_non_earthquakes():
    raw = usgs.load_fixture(FIXTURE)
    events = usgs.normalize(raw)
    # fixture holds 17 significant quakes + 10 below-threshold + 1 non-earthquake
    assert len(events) == 17
    assert all(e.hazard == "EQ" for e in events)
    assert all(
        (e.severity["mag"] or 0) >= usgs.MIN_MAG
        or (e.severity["sig"] or 0) >= usgs.MIN_SIG
        or e.severity["pager_alert"]
        for e in events
    )


def test_normalize_shapes_event():
    events = usgs.normalize(usgs.load_fixture(FIXTURE))
    e = events[0]
    assert e.uid.startswith("usgs:")
    assert e.occurred_at.endswith("Z") and "T" in e.occurred_at
    assert e.updated_at >= e.occurred_at
    src = e.sources[0]
    assert src["feed"] == "usgs"
    # the comma-wrapped `ids` string becomes a clean alias list
    assert src["id"] in src["ids"]
    assert all(i and "," not in i for i in src["ids"])
