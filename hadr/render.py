"""Render dashboard.html — the watch-floor console layout.

Stdlib only; every feed-derived string is escaped; zero JavaScript (expansion
is native <details>/<summary>). Two-pane on wide screens: a sticky overview
rail (situation, aggregates, top severity) beside dense one-line event rows
grouped by change class, everything collapsed by default.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from string import Template
from zoneinfo import ZoneInfo

from hadr.events import Event, FeedStatus
from hadr.memory import Changes

SGT = ZoneInfo("Asia/Singapore")

HAZARD_NAMES = {
    "EQ": "Earthquake", "TC": "Cyclone", "FL": "Flood", "VO": "Volcano",
    "DR": "Drought", "WF": "Wildfire", "EP": "Epidemic", "ST": "Storm",
    "TS": "Tsunami", "LS": "Landslide", "OT": "Other",
}

PAGE = Template("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HADR Situation Report</title>
<style>
  /* Tokens: light and dark are both selected (not auto-flipped); status colors
     are fixed across modes and never carry meaning without a text label. */
  :root {
    color-scheme: light dark;
    --surface: #fcfcfb; --surface-2: #ffffff; --surface-3: #f4f3f0;
    --ink: #0b0b0b; --ink-2: #52514e; --ink-3: #6e6d68;
    --border: #e4e3df; --border-strong: #cfcec9;
    --good: #0ca30c; --warning: #fab219; --serious: #ec835a; --critical: #d03b3b;
    --warning-tint: #fdf3dd; --warning-ink: #533f03;
    --accent: #2a78d6; --accent-tint: #eaf2fc;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --surface: #1a1a19; --surface-2: #232322; --surface-3: #2b2b29;
      --ink: #ffffff; --ink-2: #c3c2b7; --ink-3: #98978e;
      --border: #383835; --border-strong: #4a4945;
      --warning-tint: #33290f; --warning-ink: #f0dfae;
      --accent: #3987e5; --accent-tint: #16273d;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 0 1.5rem 3rem;
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    line-height: 1.5; background: var(--surface); color: var(--ink);
    font-variant-numeric: tabular-nums;
  }
  .page { max-width: 100rem; margin: 0 auto; }
  .dot { width: 0.6em; height: 0.6em; border-radius: 50%; display: inline-block;
         flex: none; }
  .dot.red { background: var(--critical); }
  .dot.orange { background: var(--serious); }
  .dot.yellow { background: var(--warning); }
  .dot.green { background: var(--good); }
  .dot.none { background: var(--border-strong); }

  .ops { position: sticky; top: 0; z-index: 10; display: flex; flex-wrap: wrap;
         align-items: center; gap: 0.45rem 1.1rem; font-size: 0.82rem;
         color: var(--ink-2); background: var(--surface);
         border-bottom: 1px solid var(--border); padding: 0.6rem 0.25rem;
         margin: 0 -0.25rem 1rem; }
  .ops .brand { font-weight: 700; color: var(--ink); font-size: 0.95rem; }
  .ops .sep { color: var(--border-strong); }
  .chip { display: inline-flex; align-items: center; gap: 0.4em; }
  .chip.ok::before, .chip.bad::before {
    content: ""; width: 0.55em; height: 0.55em; border-radius: 50%;
    display: inline-block; flex: none;
  }
  .chip.ok::before { background: var(--good); }
  .chip.bad::before { background: var(--critical); }
  .chip.bad { color: var(--ink); font-weight: 600; }
  .ops .stamp { margin-left: auto; color: var(--ink); font-weight: 600; }

  .banner { background: var(--warning-tint); color: var(--warning-ink);
            border: 1px solid var(--warning); border-left-width: 4px;
            border-radius: 0.5rem; padding: 0.6rem 1rem; margin: 0 0 0.8rem;
            font-size: 0.9rem; }

  .layout { display: grid; grid-template-columns: 19rem 1fr; gap: 1.25rem;
            align-items: start; }
  @media (max-width: 64rem) { .layout { grid-template-columns: 1fr; }
                              .rail { position: static; } }
  .rail { position: sticky; top: 3.4rem; display: flex; flex-direction: column;
          gap: 0.75rem; }
  .panel { border: 1px solid var(--border); border-radius: 0.6rem;
           background: var(--surface-2); padding: 0.8rem 1rem; }
  .panel h2 { margin: 0 0 0.5rem; font-size: 0.72rem; text-transform: uppercase;
              letter-spacing: 0.08em; color: var(--ink-3); font-weight: 600; }
  .panel .row { display: flex; justify-content: space-between; gap: 0.6rem;
                font-size: 0.85rem; padding: 0.16rem 0; color: var(--ink-2); }
  .panel .row b { color: var(--ink); }
  .panel .row .seg { display: inline-flex; align-items: center; gap: 0.45em;
                     min-width: 0; }
  .panel .row .seg span:last-child { overflow: hidden; text-overflow: ellipsis;
                     white-space: nowrap; }
  .lead .headline { border-left: 3px solid var(--accent); padding-left: 0.75rem;
                    font-size: 0.92rem; color: var(--ink); margin: 0.1rem 0 0.6rem; }
  .quiet { font-size: 0.9rem; color: var(--ink-2); margin: 0.1rem 0 0.6rem; }

  main h2 { font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.09em;
            color: var(--ink-3); margin: 1.4rem 0 0.55rem; font-weight: 600; }
  main section:first-child h2 { margin-top: 0.1rem; }
  main h2 .count { font-weight: 400; }

  details.ev { border: 1px solid var(--border); border-radius: 0.55rem;
               background: var(--surface-2); margin-bottom: 0.45rem;
               overflow: hidden; }
  details.ev summary { list-style: none; cursor: pointer; display: flex;
               align-items: center; gap: 0.6rem; padding: 0.5rem 0.9rem;
               font-size: 0.9rem; min-width: 0; }
  details.ev summary::-webkit-details-marker { display: none; }
  details.ev summary::after { content: "\\203A"; margin-left: auto;
               color: var(--ink-3); transform: rotate(90deg);
               transition: transform 0.15s; flex: none; }
  details.ev[open] summary::after { transform: rotate(-90deg); }
  details.ev summary:hover { background: var(--surface-3); }
  .mag { font-weight: 700; font-size: 0.78rem; min-width: 3.2em; text-align: center;
         border: 1px solid var(--border-strong); border-radius: 0.35rem;
         padding: 0.02rem 0.3rem; color: var(--ink-2); flex: none; }
  .ev .t { font-weight: 600; white-space: nowrap; overflow: hidden;
           text-overflow: ellipsis; }
  .ev .where { color: var(--ink-3); font-size: 0.8rem; white-space: nowrap;
               overflow: hidden; text-overflow: ellipsis; }
  .ev .age { color: var(--ink-3); font-size: 0.78rem; flex: none; }
  .ev .body { padding: 0.35rem 0.95rem 0.8rem 2.2rem; font-size: 0.88rem;
              color: var(--ink-2); border-top: 1px dashed var(--border); }
  .ev .body p { margin: 0.35rem 0; }
  .assess { border-left: 3px solid var(--accent); padding-left: 0.7rem;
            color: var(--ink); }
  .assess .priority { font-size: 0.68rem; text-transform: uppercase;
            font-weight: 700; letter-spacing: 0.08em; color: var(--ink-3);
            margin-right: 0.5em; }
  .links a { color: var(--accent); text-decoration: none; margin-right: 0.8em; }
  .links a:hover { text-decoration: underline; }
  .badge { font-size: 0.66rem; font-weight: 700; letter-spacing: 0.05em;
           border-radius: 0.3rem; padding: 0.06rem 0.4rem; flex: none; }
  .badge.new { background: var(--accent-tint); color: var(--accent); }
  .badge.esc { background: var(--warning-tint); color: var(--warning-ink); }

  footer { margin-top: 2.5rem; padding-top: 0.8rem;
           border-top: 1px solid var(--border); font-size: 0.78rem;
           color: var(--ink-3); }
  footer a { color: inherit; }
</style>
</head>
<body>
<div class="page">
<div class="ops">
  <span class="brand">HADR watch</span>
  $alert_summary
  <span class="sep">|</span>
  $feed_chips
  <span class="stamp">Data as of $stamp_utc UTC / $stamp_sgt SGT</span>
</div>
$banners
<div class="layout">
  <div class="rail">
    $overview
  </div>
  <main>
  $sections
  </main>
</div>
<footer>Generated unattended by the
  <a href="https://github.com/mervo/hadr-claw">hadr-claw</a> agent ·
  USGS · GDACS · ReliefWeb · click an event for its assessment</footer>
</div>
</body>
</html>
""")


def _stamp(dt: datetime) -> tuple[str, str]:
    utc = dt.astimezone(timezone.utc)
    return utc.strftime("%Y-%m-%d %H:%M"), utc.astimezone(SGT).strftime("%Y-%m-%d %H:%M")


_ALERT_RANK = {"Red": 0, "Orange": 1, "Green": 2}
_DOT = {"red": "red", "orange": "orange", "yellow": "yellow", "green": "green"}


def _dot_class(e: Event) -> str:
    for level in (e.severity.get("gdacs_alert"), e.severity.get("pager_alert")):
        cls = _DOT.get(str(level).lower())
        if cls:
            return cls
    return "none"


def _severity_key(e: Event) -> tuple:
    return (
        _ALERT_RANK.get(e.severity.get("gdacs_alert"), 3),
        -(e.severity.get("mag") or 0),
        e.occurred_at,
    )


def _age(e: Event, now: datetime) -> str:
    if not e.occurred_at:
        return ""
    occurred = datetime.fromisoformat(e.occurred_at.replace("Z", "+00:00"))
    hours = max(0, (now - occurred).total_seconds()) / 3600
    if hours < 1:
        return f"{int(hours * 60)} min"
    if hours < 48:
        return f"{hours:.0f} h"
    return f"{hours / 24:.0f} d"


def _sev_chip(e: Event) -> str:
    mag = e.severity.get("mag")
    if mag is not None:
        return f'<span class="mag">M {mag:.1f}</span>'
    return f'<span class="mag">{escape(e.hazard)}</span>'


def _where(e: Event) -> str:
    parts = []
    if e.country:
        parts.append(escape(e.country))
    elif e.lat is not None and e.lon is not None:
        parts.append(f"lat {e.lat:.1f}, lon {e.lon:.1f}")
    if e.depth_km is not None:
        parts.append(f"{e.depth_km:.0f} km deep")
    alert = e.severity.get("gdacs_alert") or e.severity.get("pager_alert")
    if alert:
        parts.append(f"{escape(str(alert))} alert")
    return " · ".join(parts) or "location n/a"


def _row(e: Event, now: datetime, badge: str = "", assessments: dict | None = None) -> str:
    badge_html = f'<span class="badge {badge}">{badge.upper()}</span>' if badge else ""
    links = "".join(
        f'<a href="{escape(s["url"], quote=True)}">{escape(s["feed"])}</a>'
        for s in e.sources
        if s.get("url")
    )
    summary = next((s["summary"] for s in e.sources if s.get("summary")), "")
    summary_html = f"<p>{escape(summary)}</p>" if summary else ""
    assess_html = ""
    if assessments and e.uid in assessments:
        a = assessments[e.uid]
        assess_html = (
            f'<p class="assess"><span class="priority">{escape(a.get("priority") or "")}'
            f"</span>{escape(a['assessment'])}</p>"
        )
    body = assess_html + summary_html + (f'<p class="links">{links}</p>' if links else "")
    return f"""<details class="ev">
  <summary><span class="dot {_dot_class(e)}"></span>{_sev_chip(e)}
    <span class="t">{escape(e.title)}</span>{badge_html}
    <span class="where">{_where(e)}</span>
    <span class="age">{_age(e, now)}</span></summary>
  <div class="body">{body or '<p>No further detail from the feeds.</p>'}</div>
</details>"""


def _section(title: str, events: list[Event], now: datetime, badge: str = "",
             assessments: dict | None = None) -> str:
    if not events:
        return ""
    rows = "\n".join(
        _row(e, now, badge, assessments) for e in sorted(events, key=_severity_key)
    )
    return (
        f'<section><h2>{escape(title)} <span class="count">· {len(events)}</span></h2>\n'
        f"{rows}</section>"
    )


def _overview(events: list[Event], changes: Changes | None, headline: str | None,
              overview: str | None, last_change_at: str | None) -> str:
    panels = []

    situation = ""
    if headline:
        situation += f'<p class="headline">{escape(headline)}</p>'
    if overview:
        situation += f'<p class="quiet">{escape(overview)}</p>'
    if changes and changes.quiet:
        since = f" since {escape(last_change_at)}" if last_change_at else ""
        situation += (
            f'<p class="quiet">No new developments{since}. '
            f"{len(changes.unchanged)} event(s) remain under watch.</p>"
        )
    if changes:
        counts = changes.counts()
        situation += "".join(
            f'<div class="row"><span>{label}</span><b>{counts[key]}</b></div>'
            for key, label in (
                ("new", "New since last report"), ("escalated", "Escalated"),
                ("updated", "Updated"), ("unchanged", "Under watch"),
            )
        )
    panels.append(f'<div class="panel lead"><h2>Situation</h2>{situation}</div>')

    hazards = Counter(e.hazard for e in events)
    if hazards:
        rows = "".join(
            f'<div class="row"><span>{escape(HAZARD_NAMES.get(hz, hz))}</span><b>{n}</b></div>'
            for hz, n in hazards.most_common()
        )
        panels.append(f'<div class="panel"><h2>By hazard</h2>{rows}</div>')

    top = sorted(events, key=_severity_key)[:3]
    if top:
        rows = "".join(
            f'<div class="row"><span class="seg"><span class="dot {_dot_class(e)}"></span>'
            f"<span>{escape(e.title)}</span></span>"
            f"<b>{escape(e.severity.get('gdacs_alert') or '')}"
            f"{f' M {m:.1f}' if (m := e.severity.get('mag')) is not None else ''}</b></div>"
            for e in top
        )
        panels.append(f'<div class="panel"><h2>Highest severity</h2>{rows}</div>')

    return "\n".join(panels)


def render(
    events: list[Event],
    statuses: list[FeedStatus],
    changes: Changes | None = None,
    generated_at: datetime | None = None,
    last_change_at: str | None = None,
    headline: str | None = None,
    overview: str | None = None,
    assessments: dict | None = None,
    notice: str | None = None,
) -> str:
    now = generated_at or datetime.now(timezone.utc)
    stamp_utc, stamp_sgt = _stamp(now)

    alerts = Counter(_dot_class(e) for e in events)
    alert_summary = "".join(
        f'<span class="chip"><span class="dot {cls}"></span>{alerts[cls]} {label}</span>'
        for cls, label in (("red", "Red"), ("orange", "Orange"), ("yellow", "Yellow"))
        if alerts.get(cls)
    ) + f'<span class="chip">{len(events)} event(s)</span>'

    feed_chips = "".join(
        f'<span class="chip {"ok" if s.ok else "bad"}">'
        f'{escape(s.feed)}: {"ok" if s.ok else "down"}'
        f'{f" · {s.latency_ms} ms" if s.latency_ms is not None else ""}</span>'
        for s in statuses
    )

    banners = f'<div class="banner">{escape(notice)}</div>' if notice else ""
    banners += "".join(
        f'<div class="banner">{escape(s.feed)} unreachable this run — {escape(s.error or "")}. '
        f"Report reflects the remaining feeds.</div>"
        for s in statuses
        if not s.ok
    )
    if not events:
        banners += '<div class="banner">No events pass the significance threshold right now.</div>'
    if changes and changes.deleted:
        banners += (
            '<div class="banner">Withdrawn by their feed while still current: '
            + ", ".join(escape(d.get("title") or d["uid"]) for d in changes.deleted)
            + "</div>"
        )

    if changes is None:
        sections = _section("Events", events, now, assessments=assessments)
    else:
        sections = "\n".join(
            filter(None, [
                _section("Escalated", changes.escalated, now, "esc", assessments),
                _section("New", changes.new, now, "new", assessments),
                _section("Updated", changes.updated, now, "", assessments),
                _section("Ongoing", changes.unchanged, now, "", assessments),
            ])
        )

    return PAGE.substitute(
        stamp_utc=stamp_utc, stamp_sgt=stamp_sgt,
        alert_summary=alert_summary, feed_chips=feed_chips, banners=banners,
        overview=_overview(events, changes, headline, overview, last_change_at),
        sections=sections,
    )


def write_dashboard(
    events: list[Event],
    statuses: list[FeedStatus],
    out: str | Path = "dashboard.html",
    changes: Changes | None = None,
    generated_at: datetime | None = None,
    last_change_at: str | None = None,
    notice: str | None = None,
) -> Path:
    out = Path(out)
    out.write_text(render(events, statuses, changes, generated_at, last_change_at, notice=notice))
    return out
