from hadr import dedupe
from hadr.__main__ import gather
from hadr.events import Event


def _crossfeed():
    events, statuses = gather(["usgs", "gdacs", "reliefweb"], "tests/fixtures/crossfeed")
    assert all(s.ok for s in statuses)
    return events


def test_one_physical_quake_from_three_feeds_merges_to_one_event():
    merged = dedupe.merge(_crossfeed())
    venezuela = [e for e in merged if e.glide == "EQ-2026-000093-VEN"]
    assert len(venezuela) == 1
    feeds = [s["feed"] for s in venezuela[0].sources]
    assert sorted(feeds) == ["gdacs", "reliefweb", "usgs"]


def test_merge_rules_are_audited():
    (venezuela,) = [e for e in dedupe.merge(_crossfeed()) if e.glide]
    rules = {s["feed"]: s.get("merged_by") for s in venezuela.sources}
    assert rules["gdacs"] is None  # primary
    assert rules["usgs"] == "spacetime"  # no shared id; matched by place+time+mag
    assert rules["reliefweb"] == "glide"


def test_canonical_uid_is_glide_and_severity_is_max():
    (venezuela,) = [e for e in dedupe.merge(_crossfeed()) if e.glide]
    assert venezuela.uid == "glide:EQ-2026-000093-VEN"
    assert venezuela.severity["gdacs_alert"] == "Red"
    assert venezuela.severity["mag"] == 7.1


def test_merge_keeps_usgs_depth_when_gdacs_is_primary():
    # GDACS events carry no depth; the merge must not drop USGS's
    (venezuela,) = [e for e in dedupe.merge(_crossfeed()) if e.glide]
    assert venezuela.depth_km == 10.0


def test_refetching_a_feed_does_not_duplicate_sources():
    events = _crossfeed()
    merged = dedupe.merge(events)
    remerged = dedupe.merge(merged + _crossfeed())
    (venezuela,) = [e for e in remerged if e.glide]
    feeds = [s["feed"] for s in venezuela.sources]
    assert sorted(feeds) == ["gdacs", "reliefweb", "usgs"], "no duplicate source rows"


def test_unrelated_event_stays_separate():
    merged = dedupe.merge(_crossfeed())
    assert len(merged) == 2
    (other,) = [e for e in merged if not e.glide]
    assert [s["feed"] for s in other.sources] == ["usgs"]


def _multihazard():
    events, statuses = gather(["gdacs", "reliefweb"], "tests/fixtures/crossfeed_multihazard")
    assert all(s.ok for s in statuses)
    return dedupe.merge(events)


def test_cyclone_merges_across_gdacs_and_reliefweb_via_glide():
    (cyclone,) = [e for e in _multihazard() if e.hazard == "TC"]
    assert cyclone.uid == "glide:TC-2026-000101-PHL"
    rules = {s["feed"]: s.get("merged_by") for s in cyclone.sources}
    assert rules == {"gdacs": None, "reliefweb": "glide"}
    assert cyclone.severity["gdacs_alert"] == "Orange"
    # the curated ReliefWeb summary must survive the merge for the assessment
    assert any(s.get("summary") for s in cyclone.sources)


def test_fresh_gdacs_flood_without_glide_stays_separate_from_reliefweb():
    # GLIDE is often empty in fresh GDACS events (ROADMAP blind spot): until it
    # arrives, the GDACS flood and the days-late ReliefWeb entry must both show
    # rather than falsely merging on country alone
    floods = [e for e in _multihazard() if e.hazard == "FL"]
    assert len(floods) == 2
    assert {e.uid for e in floods} == {"gdacs:1551201", "glide:FL-2026-000102-BGD"}


def test_spacetime_never_matches_on_missing_timestamps():
    base = dict(
        hazard="FL", title="t", updated_at="", lat=23.7, lon=90.4,
        severity={}, sources=[],
    )
    a = Event(uid="a:1", occurred_at="", **{**base, "sources": [{"feed": "x", "id": "1", "ids": []}]})
    b = Event(uid="b:2", occurred_at="", **{**base, "sources": [{"feed": "y", "id": "2", "ids": []}]})
    assert len(dedupe.merge([a, b])) == 2, "missing times must not merge on place alone"
