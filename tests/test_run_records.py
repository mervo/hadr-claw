from pathlib import Path

from hadr.__main__ import main


def test_run_records_follow_the_state_dir(tmp_path, monkeypatch):
    """A run pointed at a scratch --state must not write into the repo's
    committed state/runs (dev PRs must not diff state/**)."""
    monkeypatch.chdir(Path(__file__).parent.parent)
    state = tmp_path / "scratch" / "seen.json"
    out = tmp_path / "dash.html"
    repo_runs_before = sorted(Path("state/runs").glob("*.json"))

    main(["--fixtures", "tests/fixtures", "--state", str(state), "--out", str(out)])

    assert sorted(Path("state/runs").glob("*.json")) == repo_runs_before
    assert list((tmp_path / "scratch" / "runs").glob("*.json")), "record lands beside the state"
