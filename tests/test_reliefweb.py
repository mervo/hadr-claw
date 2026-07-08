from pathlib import Path

from hadr.feeds import reliefweb

FIXTURE = Path(__file__).parent / "fixtures" / "reliefweb" / "rss.xml"


def test_normalize_extracts_glide_hazard_country():
    events = reliefweb.normalize(reliefweb.load_fixture(FIXTURE))
    assert len(events) == 8
    for e in events:
        assert e.glide, "every fixture entry carries a GLIDE"
        assert e.uid == f"reliefweb:{e.glide}"
        assert e.hazard == e.glide.split("-")[0]
        assert e.lat is None and e.lon is None


def test_glide_from_slug_matches_description():
    events = reliefweb.normalize(reliefweb.load_fixture(FIXTURE))
    for e in events:
        slug = e.sources[0]["url"].rstrip("/").rsplit("/", 1)[-1].upper()
        assert e.glide == slug, "GLIDE in description must agree with the link slug"


def test_summary_prose_is_clean_of_tags_and_boilerplate():
    events = reliefweb.normalize(reliefweb.load_fixture(FIXTURE))
    for e in events:
        summary = e.sources[0]["summary"]
        assert "<" not in summary
        assert "Glide:" not in summary
