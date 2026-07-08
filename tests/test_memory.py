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


def test_re_escalation_after_a_dip_is_escalated_again():
    base = dict(
        hazard="EQ", title="t", occurred_at="2026-07-07T18:00:00Z",
        updated_at="2026-07-07T18:00:00Z", lat=1.0, lon=1.0,
        sources=[{"feed": "gdacs", "id": "9", "ids": ["9"], "url": None}],
    )

    def event(alert):
        return [Event(uid="gdacs:9", severity={"gdacs_alert": alert}, **base)]

    state = memory.load("/nonexistent")
    memory.diff(state, event("Orange"), now=NOW)                 # first sight
    dipped = memory.diff(state, event("Green"), now=NOW)         # de-escalation
    assert not dipped.escalated
    risen = memory.diff(state, event("Orange"), now=NOW)         # back up
    assert len(risen.escalated) == 1, "re-escalation to a previous peak must surface"


def test_pruning_drops_stale_inactive_entries():
    state = _day1_state()
    memory.diff(state, _events("day2"), now=NOW)  # marks deleted/aged_out
    from datetime import timedelta

    later = NOW + timedelta(days=memory.PRUNE_AFTER_DAYS + 1)
    memory.diff(state, [], now=later)
    statuses = {e.get("status") for e in state["events"].values()}
    assert statuses <= {"deleted", "aged_out", "active"}
    assert not any(
        e for e in state["events"].values()
        if e.get("status") != "active" and e["last_seen"] < "2026-07-09"
    ), "inactive entries unseen for PRUNE_AFTER_DAYS are dropped"


def test_fingerprint_survives_metre_scale_revisions():
    kwargs = dict(
        hazard="EQ", title="t", occurred_at="x", updated_at="x",
        severity={"mag": 5.03}, sources=[{"feed": "usgs", "id": "1", "ids": ["1"]}],
    )
    a = Event(uid="u", lat=10.001, lon=20.001, **kwargs)
    b = Event(uid="u", lat=10.004, lon=19.999, **kwargs)
    assert memory.fingerprint(a) == memory.fingerprint(b)


def test_pager_outranking_gdacs_does_not_escalate_forever():
    # GDACS says Green but PAGER says orange: alert_rank takes the max, so the
    # recorded label must too — recording "Green" would read as an escalation
    # on every subsequent run
    base = dict(
        hazard="EQ", title="t", occurred_at="2026-07-07T18:00:00Z",
        updated_at="2026-07-07T18:00:00Z", lat=1.0, lon=1.0,
        severity={"gdacs_alert": "Green", "pager_alert": "orange"},
        sources=[{"feed": "gdacs", "id": "9", "ids": ["9"], "url": None}],
    )
    state = memory.load("/nonexistent")
    memory.diff(state, [Event(uid="gdacs:9", **base)], now=NOW)
    assert state["events"]["gdacs:9"]["alert_history"][-1][1] == "orange"
    rerun = memory.diff(state, [Event(uid="gdacs:9", **base)], now=NOW)
    assert rerun.quiet, "identical event must not re-escalate"


def test_state_round_trips(tmp_path):
    state = _day1_state()
    path = tmp_path / "seen.json"
    memory.save(state, path)
    assert memory.load(path) == state
