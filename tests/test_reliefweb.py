from pathlib import Path

from hadr.feeds import reliefweb

FIXTURE = Path(__file__).parent / "fixtures" / "reliefweb" / "rss.xml"


def test_normalize_extracts_glide_hazard_country():
    events = reliefweb.normalize(reliefweb.load_fixture(FIXTURE))
    assert len(events) == 9
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


def test_bare_entry_survives_without_crashing_the_feed():
    """An entry stripped of description/GLIDE/date still normalizes (curated
    entries are always kept) and never takes healthy neighbors down."""
    raw = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0"><channel><title>t</title>
    <item><title>Bare entry, no description or link</title></item>
    <item>
      <title>Flood - Testland</title>
      <link>https://reliefweb.int/disaster/fl-2026-000123-tst</link>
      <description>Affected country: Testland Glide: FL-2026-000123-TST</description>
      <pubDate>Tue, 07 Jul 2026 00:00:00 +0000</pubDate>
    </item>
    </channel></rss>"""
    events = reliefweb.normalize(raw)
    assert len(events) == 2
    assert any(e.glide == "FL-2026-000123-TST" for e in events)
    bare = next(e for e in events if not e.glide)
    assert bare.hazard == "OT" and bare.occurred_at == ""


def test_summary_prose_is_clean_of_tags_and_boilerplate():
    events = reliefweb.normalize(reliefweb.load_fixture(FIXTURE))
    for e in events:
        summary = e.sources[0]["summary"]
        assert "<" not in summary
        assert "Glide:" not in summary


def test_volcano_extracted_from_fixture():
    """Volcano entries should be properly normalized from ReliefWeb."""
    events = reliefweb.normalize(reliefweb.load_fixture(FIXTURE))
    volcanoes = [e for e in events if e.hazard == "VO"]
    assert len(volcanoes) >= 1
    vo = volcanoes[0]
    assert vo.glide.startswith("VO-2026-")
    assert "Mount Merapi" in vo.title or "Merapi" in vo.title


def test_epidemic_extracted_from_fixture():
    """Epidemic/disease outbreak entries (EP hazard code) should be extracted."""
    events = reliefweb.normalize(reliefweb.load_fixture(FIXTURE))
    epidemics = [e for e in events if e.hazard == "EP"]
    assert len(epidemics) >= 2, "fixture should have Ebola and Dengue outbreaks"
    # Test Ebola outbreak
    ebola = next((e for e in epidemics if "Ebola" in e.title or "Bundibugyo" in e.title), None)
    assert ebola is not None
    assert ebola.glide.startswith("EP-2026-") and "COD" in ebola.glide
    # Test Dengue outbreak
    dengue = next((e for e in epidemics if "Dengue" in e.title), None)
    assert dengue is not None
    assert dengue.glide.startswith("EP-2026-") and "LKA" in dengue.glide


def test_storm_hailstorm_extracted_from_fixture():
    """Storm/hailstorm entries (ST hazard code) should be extracted."""
    events = reliefweb.normalize(reliefweb.load_fixture(FIXTURE))
    storms = [e for e in events if e.hazard == "ST"]
    assert len(storms) >= 1, "fixture should have at least one storm entry"
    storm = storms[0]
    assert storm.glide.startswith("ST-2026-")
    assert "hailstorm" in storm.title.lower() or "Armenia" in storm.title
