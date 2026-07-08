import json

import pytest

from agent import morning, tools
from hadr.events import Event
from hadr.memory import Changes

TRANSCRIPT = "tests/fixtures/transcripts/morning.json"


@pytest.fixture(autouse=True)
def session(monkeypatch, tmp_path):
    tools.reset()
    monkeypatch.setenv("HADR_SPANS_FILE", str(tmp_path / "spans.jsonl"))
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    return tmp_path


def _run(tmp_path, fake_model=None, monkeypatch=None):
    if fake_model:
        monkeypatch.setenv("HADR_FAKE_MODEL", fake_model)
    out = tmp_path / "dash.html"
    state = tmp_path / "state" / "seen.json"
    morning.main(["--fixtures", "tests/fixtures", "--out", str(out), "--state", str(state)])
    record = json.loads((tmp_path / "state" / "last_run.json").read_text())
    return out, state, record


def test_agentic_replay_produces_assessed_report(session, monkeypatch):
    out, _state, record = _run(session, TRANSCRIPT, monkeypatch)
    assert record["engine"] == "agentic"
    html = out.read_text()
    assert 'class="assess"' in html
    assert 'class="panel lead"' in html, "the situation panel carries the model lead"
    assert "Data as of" in html


def test_model_never_writing_dashboard_triggers_fallback(session, monkeypatch):
    silent = session / "silent.json"
    silent.write_text(json.dumps({"tools_hash": None, "turns": [
        {"role": "assistant", "content": "I have nothing further."}
    ]}))
    out, _state, record = _run(session, str(silent), monkeypatch)
    assert record["engine"] == "fallback"
    html = out.read_text()
    assert "Automated assessment unavailable" in html
    assert "Data as of" in html, "the fallback report still exists and is fresh"


def test_second_run_is_quiet_and_skips_the_model(session, monkeypatch):
    _run(session, TRANSCRIPT, monkeypatch)
    # a broken fake model proves the quiet path never touches it
    broken = session / "broken.json"
    broken.write_text(json.dumps({"tools_hash": None, "turns": []}))
    monkeypatch.setenv("HADR_FAKE_MODEL", str(broken))
    out, _state, record = _run(session, monkeypatch=monkeypatch)
    assert record["engine"] == "pipeline-quiet"
    assert "No new developments" in out.read_text()


def test_run_record_carries_caps_and_observability_fields(session, monkeypatch):
    _out, state, _ = _run(session, TRANSCRIPT, monkeypatch)
    runs = sorted((state.parent / "runs").glob("[0-9]*Z.json"))
    record = json.loads(runs[-1].read_text())
    for key in ("caps", "turns", "tokens", "engine", "model", "cap_tripped", "changes"):
        assert key in record
    transcripts = list((state.parent / "runs").glob("*-transcript.json"))
    assert transcripts, "agentic runs save their transcript"
    assert (session / "spans.jsonl").exists(), "file span exporter wrote traces"


def test_briefing_prioritizes_reliefweb_summary():
    """Verify that the briefing prefers ReliefWeb's curated summary over other sources."""
    # Create a merged event with both GDACS and ReliefWeb sources
    merged_event = Event(
        uid="glide:EQ-2026-000001-IDN",
        hazard="EQ",
        title="Earthquake in Indonesia",
        occurred_at="2026-07-08T10:00:00Z",
        updated_at="2026-07-08T10:00:00Z",
        lat=0.5,
        lon=101.0,
        severity={"gdacs_alert": "Orange", "mag": 6.5},
        glide="EQ-2026-000001-IDN",
        sources=[
            {"feed": "gdacs", "id": "123456", "ids": ["123456"]},
            {
                "feed": "reliefweb",
                "id": "EQ-2026-000001-IDN",
                "ids": ["EQ-2026-000001-IDN"],
                "summary": "Powerful earthquake struck central Indonesia. Significant damage and casualties reported."
            }
        ]
    )

    # Create a Changes object with this event as new
    changes = Changes(new=[merged_event])

    # Get the briefing (internal function, but we can call it through the module)
    briefing_text = morning._briefing(changes)

    # Verify ReliefWeb's summary is in the briefing
    assert "Significant damage and casualties reported" in briefing_text
    briefing_json = json.loads(briefing_text.split("Morning situation report run. Changes since the last report: ")[1].split("\nAll events")[0])
    assert briefing_json["new"][0]["summary"] == "Powerful earthquake struck central Indonesia. Significant damage and casualties reported."


def test_briefing_identifies_deescalated_events():
    """Verify that de-escalated events (alert level decreased) are identified in the briefing."""
    # Create an event that was Red and is now Orange
    deescalated_event = Event(
        uid="gdacs:12345",
        hazard="EQ",
        title="Earthquake in Turkey",
        occurred_at="2026-07-07T18:00:00Z",
        updated_at="2026-07-08T10:00:00Z",
        lat=39.0,
        lon=32.0,
        severity={"gdacs_alert": "Orange", "mag": 6.5},
        sources=[{"feed": "gdacs", "id": "12345", "ids": ["12345"], "url": None}],
    )

    # Create state with alert history showing Red -> Orange de-escalation
    state = {
        "version": 1,
        "updated_at": None,
        "events": {
            "gdacs:12345": {
                "first_seen": "2026-07-07T18:00:00Z",
                "last_seen": "2026-07-08T10:00:00Z",
                "occurred_at": "2026-07-07T18:00:00Z",
                "alert_history": [
                    ["2026-07-07T18:00:00Z", "Red"],
                    ["2026-07-08T10:00:00Z", "Orange"]
                ],
                "aliases": ["gdacs:12345"],
                "feeds": ["gdacs"],
                "status": "active",
                "title": "Earthquake in Turkey",
                "fingerprint": "sha256:old"
            }
        }
    }

    # Create Changes with this event as updated (fingerprint changed)
    changes = Changes(updated=[deescalated_event])

    # Get the briefing with state
    briefing_text = morning._briefing(changes, state)

    # Verify de-escalated event is in the briefing under deescalated key
    briefing_json = json.loads(briefing_text.split("Morning situation report run. Changes since the last report: ")[1].split("\nAll events")[0])
    assert "deescalated" in briefing_json
    assert len(briefing_json["deescalated"]) == 1
    assert briefing_json["deescalated"][0]["uid"] == "gdacs:12345"
    assert briefing_json["deescalated"][0]["severity"]["gdacs_alert"] == "Orange"

    # Verify the prompt mentions de-escalated events
    assert "de-escalated" in briefing_text
    assert "Assess the escalated, new, and de-escalated events" in briefing_text
