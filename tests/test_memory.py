from datetime import datetime, timezone

from hadr import dedupe, memory
from hadr.__main__ import gather
from hadr.events import Event

NOW = datetime(2026, 7, 8, 0, 0, tzinfo=timezone.utc)


def _events(day):
    events, statuses = gather(["usgs", "gdacs"], f"tests/fixtures/{day}")
    assert all(s.ok for s in statuses)
    return dedupe.merge(events)


def _day1_state():
    state = memory.load("/nonexistent")
    memory.diff(state, _events("day1"), now=NOW)
    return state


def test_first_sight_is_all_new():
    state = memory.load("/nonexistent")
    changes = memory.diff(state, _events("day1"), now=NOW)
    assert changes.counts() == {"new": 5, "escalated": 0, "updated": 0, "unchanged": 0, "deleted": 0}


def test_rerun_on_same_data_is_quiet():
    state = _day1_state()
    changes = memory.diff(state, _events("day1"), now=NOW)
    assert changes.quiet
    assert len(changes.unchanged) == 5


def test_day2_classifies_every_change_kind():
    state = _day1_state()
    changes = memory.diff(state, _events("day2"), now=NOW)

    assert [e.title for e in changes.escalated] == ["Earthquake in Malaysia"]  # Green -> Orange
    assert [e.uid for e in changes.new] == ["usgs:usday0004"]
    assert [e.uid for e in changes.updated] == ["usgs:usday0005"]  # mag 5.0 -> 5.4
    assert [e.uid for e in changes.unchanged] == ["usgs:usday0001"]
    # gone while still inside the 24 h window -> deleted; older -> silently aged out
    assert [d["uid"] for d in changes.deleted] == ["usgs:usday0003"]
    assert state["events"]["usgs:usday0002"]["status"] == "aged_out"


def test_uid_rename_via_alias_is_not_a_new_event():
    base = dict(
        hazard="EQ", title="t", occurred_at="2026-07-07T18:00:00Z",
        updated_at="2026-07-07T18:00:00Z", lat=1.0, lon=1.0,
        severity={"gdacs_alert": "Orange"},
        sources=[{"feed": "gdacs", "id": "9", "ids": ["9"], "url": None}],
    )
    state = memory.load("/nonexistent")
    memory.diff(state, [Event(uid="gdacs:9", **base)], now=NOW)
    # a GLIDE arrives late: canonical uid changes but source ids overlap
    changes = memory.diff(
        state, [Event(uid="glide:EQ-2026-000199-XYZ", glide="EQ-2026-000199-XYZ", **base)], now=NOW
    )
    assert not changes.new
    assert "glide:EQ-2026-000199-XYZ" in state["events"]
    assert "gdacs:9" not in state["events"]


def test_fingerprint_survives_metre_scale_revisions():
    kwargs = dict(
        hazard="EQ", title="t", occurred_at="x", updated_at="x",
        severity={"mag": 5.03}, sources=[{"feed": "usgs", "id": "1", "ids": ["1"]}],
    )
    a = Event(uid="u", lat=10.001, lon=20.001, **kwargs)
    b = Event(uid="u", lat=10.004, lon=19.999, **kwargs)
    assert memory.fingerprint(a) == memory.fingerprint(b)


def test_state_round_trips(tmp_path):
    state = _day1_state()
    path = tmp_path / "seen.json"
    memory.save(state, path)
    assert memory.load(path) == state
