"""ReliefWeb disasters via RSS (see feeds/reliefweb.md).

RSS needs no appname approval. Entries are human-curated and days late; they
carry no coordinates, and pubDate is the creation date (midnight) — change
detection must fingerprint the description text, not the date. The JSON API
can slot in behind normalize() once the appname is approved.
"""

from __future__ import annotations

import re
from html import unescape
from pathlib import Path

import feedparser
import httpx

from hadr import USER_AGENT
from hadr.events import Event

URL = "https://reliefweb.int/disasters/rss.xml"
FIXTURE_NAME = "rss.xml"
WINDOW_HOURS = None

_GLIDE_IN_DESC = re.compile(r"Glide:\s*([A-Z0-9-]+)")
_COUNTRY_IN_DESC = re.compile(r"Affected countr(?:y|ies):\s*([^<]+)")
_TAGS = re.compile(r"<[^>]+>")
SUMMARY_CHARS = 600


def fetch_raw() -> str:
    with httpx.Client(
        follow_redirects=True, timeout=30, headers={"User-Agent": USER_AGENT}
    ) as client:
        resp = client.get(URL)
        resp.raise_for_status()
        return resp.text


def load_fixture(path: str | Path) -> str:
    return Path(path).read_text()


def _glide(entry) -> str | None:
    """GLIDE appears twice — in the description tag and the link slug. The two
    should agree; the description wins, the slug is the fallback."""
    desc = unescape(entry.get("description", ""))
    from_desc = _GLIDE_IN_DESC.search(desc)
    if from_desc:
        return from_desc.group(1)
    slug = entry.get("link", "").rstrip("/").rsplit("/", 1)[-1]
    return slug.upper() if re.fullmatch(r"[a-z]{2}-\d{4}-\d{6}-[a-z]{3}", slug) else None


def _prose(desc: str) -> str:
    text = _TAGS.sub(" ", unescape(desc))
    text = re.sub(r"Affected countr(?:y|ies):[^<]*?(?=Glide:|$)", " ", text)
    text = re.sub(r"Glide:\s*[A-Z0-9-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()[:SUMMARY_CHARS]


def _iso(entry) -> str:
    parsed = entry.get("published_parsed")
    if not parsed:
        return ""
    return f"{parsed.tm_year:04}-{parsed.tm_mon:02}-{parsed.tm_mday:02}T00:00:00Z"


def normalize(raw: str) -> list[Event]:
    events = []
    for entry in feedparser.parse(raw).entries:
        glide = _glide(entry)
        desc = unescape(entry.get("description", ""))
        country_match = _COUNTRY_IN_DESC.search(desc)
        occurred = _iso(entry)
        events.append(
            Event(
                uid=f"reliefweb:{glide or entry.get('link', entry.get('title', ''))}",
                hazard=glide.split("-")[0] if glide else "OT",
                title=entry.get("title", ""),
                occurred_at=occurred,
                updated_at=occurred,
                lat=None,
                lon=None,
                country=country_match.group(1).strip() if country_match else None,
                severity={"curated": True},
                glide=glide,
                sources=[
                    {
                        "feed": "reliefweb",
                        "id": glide or entry.get("link", ""),
                        "ids": [glide] if glide else [],
                        "url": entry.get("link"),
                        "summary": _prose(entry.get("description", "")),
                    }
                ],
            )
        )
    return events
