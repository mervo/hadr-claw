from hadr import dedupe
from hadr.__main__ import gather


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


def test_unrelated_event_stays_separate():
    merged = dedupe.merge(_crossfeed())
    assert len(merged) == 2
    (other,) = [e for e in merged if not e.glide]
    assert [s["feed"] for s in other.sources] == ["usgs"]
