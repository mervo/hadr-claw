"""Test normalizers handle degraded/edge-case payloads gracefully.

Holdout fixtures will have incomplete fields, missing timestamps,
malformed data. These tests verify we skip bad entries and salvage good ones."""

from pathlib import Path

from hadr.feeds import gdacs, reliefweb, usgs

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "degraded_payloads"


def test_gdacs_handles_empty_glide():
    """GDACS events with empty GLIDE should normalize (not merge on GLIDE rule)."""
    events = gdacs.normalize(gdacs.load_fixture(FIXTURES_DIR / "gdacs" / "events.json"))
    # Should have all 3 events (empty glide is tolerated, just not matched)
    assert len(events) == 3
    empty_glide = [e for e in events if e.uid == "gdacs:1550601"]
    assert len(empty_glide) == 1
    assert empty_glide[0].glide is None or empty_glide[0].glide == ""


def test_gdacs_handles_null_country_iso3():
    """GDACS events with null country/iso3 should still normalize."""
    events = gdacs.normalize(gdacs.load_fixture(FIXTURES_DIR / "gdacs" / "events.json"))
    empty_country = [e for e in events if e.uid == "gdacs:1550601"]
    assert len(empty_country) == 1
    # country and iso3 are allowed to be None
    assert empty_country[0].country is None
    assert empty_country[0].iso3 is None


def test_gdacs_handles_empty_title():
    """GDACS events with empty name field should default to empty string."""
    events = gdacs.normalize(gdacs.load_fixture(FIXTURES_DIR / "gdacs" / "events.json"))
    empty_title = [e for e in events if e.uid == "gdacs:1550602"]
    assert len(empty_title) == 1
    # Empty title is allowed (defaulted to "")
    assert empty_title[0].title == ""


def test_gdacs_handles_null_glide():
    """GDACS events with null glide should normalize to None."""
    events = gdacs.normalize(gdacs.load_fixture(FIXTURES_DIR / "gdacs" / "events.json"))
    null_glide = [e for e in events if e.uid == "gdacs:1550603"]
    assert len(null_glide) == 1
    assert null_glide[0].glide is None


def test_reliefweb_handles_missing_pubdate():
    """ReliefWeb entries without pubDate should have empty timestamp."""
    events = reliefweb.normalize(reliefweb.load_fixture(FIXTURES_DIR / "reliefweb" / "rss.xml"))
    # Should have 4 events (no entries skipped)
    assert len(events) == 4
    # Entry without pubDate (Bangladesh floods) should have empty occurred_at
    bangla = [e for e in events if "BGD" in (e.glide or "")]
    assert len(bangla) == 1
    assert bangla[0].occurred_at == ""


def test_reliefweb_handles_missing_glide():
    """ReliefWeb entries without GLIDE should normalize with hazard OT."""
    events = reliefweb.normalize(reliefweb.load_fixture(FIXTURES_DIR / "reliefweb" / "rss.xml"))
    no_glide = [e for e in events if e.glide is None]
    assert len(no_glide) == 1
    assert no_glide[0].hazard == "OT"  # Default when no GLIDE


def test_reliefweb_extracts_all_entries():
    """ReliefWeb should extract all entries (even with degraded fields)."""
    events = reliefweb.normalize(reliefweb.load_fixture(FIXTURES_DIR / "reliefweb" / "rss.xml"))
    assert len(events) == 4
    glides = {e.glide for e in events}
    assert "TC-2026-000150-PHL" in glides
    assert "FL-2026-000145-NPL" in glides
    assert "FL-2026-000140-BGD" in glides


def test_usgs_handles_3d_coordinates():
    """USGS features with 3D coordinates (depth) should extract depth_km."""
    events = usgs.normalize(usgs.load_fixture(FIXTURES_DIR / "usgs" / "all_day.geojson"))
    assert len(events) == 2
    with_depth = [e for e in events if e.uid == "usgs:us6000tafd"]
    assert len(with_depth) == 1
    assert with_depth[0].depth_km == 15.2


def test_usgs_handles_2d_coordinates():
    """USGS features with 2D coordinates (no depth) should have None depth."""
    events = usgs.normalize(usgs.load_fixture(FIXTURES_DIR / "usgs" / "all_day.geojson"))
    no_depth = [e for e in events if e.uid == "usgs:us6000taaa"]
    assert len(no_depth) == 1
    assert no_depth[0].depth_km is None
