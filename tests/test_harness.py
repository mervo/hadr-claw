import json

import pytest

from agent import tools
from agent.harness import SOUL, run_turn
from agent.model import FakeModel

TRANSCRIPT = "tests/fixtures/transcripts/report.json"


@pytest.fixture(autouse=True)
def session(monkeypatch, tmp_path):
    tools.reset()
    monkeypatch.setenv("HADR_FIXTURES", "tests/fixtures")
    out = tmp_path / "dash.html"
    monkeypatch.setenv("HADR_DASHBOARD_OUT", str(out))
    return out


def _messages():
    return [
        {"role": "system", "content": SOUL.read_text()},
        {"role": "user", "content": "check the quake feeds and write me a dashboard"},
    ]


def test_replay_runs_both_tools_and_terminates(session):
    reply = run_turn(FakeModel(TRANSCRIPT), _messages())
    assert reply.get("content"), "loop must end with a final assistant message"
    html = session.read_text()
    assert "Data as of" in html
    assert 'class="assess"' in html, "model assessments must appear on the cards"


def test_replay_shows_uid_guard_self_correction(session):
    # the recorded live session had write_dashboard rejected before succeeding —
    # replaying proves the error-feedback path drives the model to correct itself
    messages = _messages()
    run_turn(FakeModel(TRANSCRIPT), messages)
    tool_results = [m["content"] for m in messages if m.get("role") == "tool"]
    rejections = [r for r in tool_results if '"ok": false' in r]
    successes = [r for r in tool_results if '"ok": true' in r]
    assert rejections, "transcript should include at least one rejected write"
    assert len(successes) == 1, "exactly one dashboard write must succeed"


def test_stale_tool_schema_fails_loudly():
    model = FakeModel(TRANSCRIPT)
    changed = [{"type": "function", "function": {"name": "renamed_tool", "parameters": {}}}]
    with pytest.raises(RuntimeError, match="different tool schemas"):
        model.complete([], tools=changed)


def test_write_dashboard_rejects_invented_events(session):
    tools.fetch_feed("usgs")
    result = json.loads(
        tools.write_dashboard(
            headline="h", overview="o",
            assessments=[{"uid": "usgs:doesnotexist", "assessment": "x", "priority": "low"}],
        )
    )
    assert result["ok"] is False
    assert "usgs:doesnotexist" in result["error"]
