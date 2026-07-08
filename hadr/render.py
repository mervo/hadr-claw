"""Render dashboard.html. Stdlib only; every feed-derived string is escaped."""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from pathlib import Path
from string import Template
from zoneinfo import ZoneInfo

from hadr.events import Event, FeedStatus

SGT = ZoneInfo("Asia/Singapore")

PAGE = Template("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HADR Situation Report</title>
<style>
  :root { color-scheme: light dark; font-family: system-ui, sans-serif; }
  body { margin: 0 auto; max-width: 60rem; padding: 1rem; line-height: 1.45; }
  header h1 { margin-bottom: 0.2rem; }
  .stamp { color: #666; }
  .ops { display: flex; flex-wrap: wrap; gap: 0.5rem; margin: 0.8rem 0 1.2rem;
         font-size: 0.85rem; }
  .chip { border-radius: 1rem; padding: 0.15rem 0.7rem; background: #e8e8e8; color: #222; }
  .chip.ok { background: #d3f0d3; }
  .chip.bad { background: #f6d3d3; }
  .card { border: 1px solid #ccc; border-radius: 0.5rem; padding: 0.7rem 1rem;
          margin-bottom: 0.8rem; }
  .card h2 { margin: 0 0 0.3rem; font-size: 1.05rem; }
  .mag { display: inline-block; min-width: 2.6rem; text-align: center; font-weight: bold;
         border-radius: 0.4rem; padding: 0.1rem 0.4rem; margin-right: 0.5rem;
         background: #ffd9a0; color: #222; }
  .alert { display: inline-block; font-weight: bold; border-radius: 0.4rem;
           padding: 0.1rem 0.5rem; margin-right: 0.5rem; color: #fff; }
  .alert.Red { background: #c62828; } .alert.Orange { background: #ef6c00; }
  .alert.Green { background: #2e7d32; }
  .hazard { font-size: 0.75rem; letter-spacing: 0.05em; color: #777; margin-right: 0.5rem; }
  .meta { font-size: 0.85rem; color: #555; }
  .banner { background: #fff3cd; color: #533f03; border: 1px solid #e6d9a8;
            border-radius: 0.5rem; padding: 0.6rem 1rem; margin-bottom: 1rem; }
  a { color: inherit; }
</style>
</head>
<body>
<header>
  <h1>HADR Situation Report</h1>
  <p class="stamp">Data as of $stamp_utc UTC / $stamp_sgt SGT</p>
</header>
<div class="ops">$ops_chips</div>
$banners
<main>
$cards
</main>
</body>
</html>
""")


def _stamp(dt: datetime) -> tuple[str, str]:
    utc = dt.astimezone(timezone.utc)
    return utc.strftime("%Y-%m-%d %H:%M"), utc.astimezone(SGT).strftime("%Y-%m-%d %H:%M")


_ALERT_RANK = {"Red": 0, "Orange": 1, "Green": 2}


def _severity_key(e: Event) -> tuple:
    return (
        _ALERT_RANK.get(e.severity.get("gdacs_alert"), 3),
        -(e.severity.get("mag") or 0),
        e.occurred_at,
    )


def _card(e: Event) -> str:
    alert = e.severity.get("gdacs_alert")
    badges = ""
    if alert in _ALERT_RANK:
        badges += f'<span class="alert {alert}">{alert}</span>'
    mag = e.severity.get("mag")
    if mag is not None:
        badges += f'<span class="mag">M {escape(str(mag))}</span>'
    links = " · ".join(
        f'<a href="{escape(s["url"], quote=True)}">{escape(s["feed"])}</a>'
        for s in e.sources
        if s.get("url")
    )
    place = (
        f"lat {e.lat:.2f}, lon {e.lon:.2f}"
        if e.lat is not None and e.lon is not None
        else escape(e.country or "location n/a")
    )
    depth = f" · depth {e.depth_km:.0f} km" if e.depth_km is not None else ""
    summary = next((s["summary"] for s in e.sources if s.get("summary")), "")
    summary_html = f"<p>{escape(summary)}</p>" if summary else ""
    return f"""<div class="card">
  <h2><span class="hazard">{escape(e.hazard)}</span>{badges}{escape(e.title)}</h2>
  <p class="meta">{escape(e.occurred_at)} · {place}{depth} · {links}</p>
  {summary_html}
</div>"""


def render(
    events: list[Event], statuses: list[FeedStatus], generated_at: datetime | None = None
) -> str:
    now = generated_at or datetime.now(timezone.utc)
    stamp_utc, stamp_sgt = _stamp(now)

    chips = [
        f'<span class="chip {"ok" if s.ok else "bad"}">'
        f'{escape(s.feed)}: {"ok" if s.ok else "down"}'
        f'{f" · {s.latency_ms} ms" if s.latency_ms is not None else ""}</span>'
        for s in statuses
    ]
    chips.append(f'<span class="chip">{len(events)} significant event(s)</span>')

    banners = "".join(
        f'<div class="banner">{escape(s.feed)} unreachable this run — {escape(s.error or "")}. '
        f"Report reflects the remaining feeds.</div>"
        for s in statuses
        if not s.ok
    )
    if not events:
        banners += '<div class="banner">No events pass the significance threshold right now.</div>'

    cards = "\n".join(_card(e) for e in sorted(events, key=_severity_key))
    return PAGE.substitute(
        stamp_utc=stamp_utc, stamp_sgt=stamp_sgt, ops_chips="\n".join(chips),
        banners=banners, cards=cards,
    )


def write_dashboard(
    events: list[Event],
    statuses: list[FeedStatus],
    out: str | Path = "dashboard.html",
    generated_at: datetime | None = None,
) -> Path:
    out = Path(out)
    out.write_text(render(events, statuses, generated_at))
    return out
