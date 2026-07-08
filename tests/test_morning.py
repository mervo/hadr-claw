import json

import pytest

from agent import morning, tools

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
