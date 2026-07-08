"""Render dashboard.html. Stdlib only; every feed-derived string is escaped."""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from pathlib import Path
from string import Template
from zoneinfo import ZoneInfo

from hadr.events import Event, FeedStatus
from hadr.memory import Changes

SGT = ZoneInfo("Asia/Singapore")

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
    --surface: #fcfcfb; --surface-2: #ffffff;
    --ink: #0b0b0b; --ink-2: #52514e; --ink-3: #6e6d68;
    --border: #e4e3df; --border-strong: #cfcec9;
    --good: #0ca30c; --warning: #fab219; --serious: #ec835a; --critical: #d03b3b;
    --warning-tint: #fdf3dd; --warning-ink: #533f03;
    --accent: #2a78d6;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --surface: #1a1a19; --surface-2: #232322;
      --ink: #ffffff; --ink-2: #c3c2b7; --ink-3: #98978e;
      --border: #383835; --border-strong: #4a4945;
      --warning-tint: #33290f; --warning-ink: #f0dfae;
      --accent: #3987e5;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0 auto; max-width: 60rem; padding: 1.5rem 1.25rem 3rem;
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    line-height: 1.55; background: var(--surface); color: var(--ink);
    font-variant-numeric: tabular-nums;
  }
  header { margin-bottom: 0.5rem; }
  header h1 { margin: 0 0 0.15rem; font-size: 1.45rem; letter-spacing: -0.01em; }
  header .sub { margin: 0; color: var(--ink-3); font-size: 0.85rem; }
  .stamp { color: var(--ink-2); font-size: 0.9rem; margin: 0.35rem 0 0; }
  .ops { display: flex; flex-wrap: wrap; gap: 0.5rem; margin: 1rem 0 1.5rem;
         font-size: 0.8rem; }
  .chip { display: inline-flex; align-items: center; gap: 0.4em;
          border: 1px solid var(--border); border-radius: 999px;
          padding: 0.2rem 0.75rem; color: var(--ink-2); background: var(--surface-2); }
  .chip.ok::before, .chip.bad::before, .alert::before {
    content: ""; width: 0.55em; height: 0.55em; border-radius: 50%;
    display: inline-block; flex: none;
  }
  .chip.ok::before { background: var(--good); }
  .chip.bad::before { background: var(--critical); }
  .chip.bad { color: var(--ink); border-color: var(--border-strong); }
  main h2 { font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.09em;
            color: var(--ink-3); margin: 1.75rem 0 0.6rem; font-weight: 600; }
  main h2 .count { color: var(--ink-3); font-weight: 400; }
  .card { border: 1px solid var(--border); border-radius: 0.6rem;
          padding: 0.85rem 1.1rem; margin-bottom: 0.7rem; background: var(--surface-2); }
  .card h3 { margin: 0 0 0.35rem; font-size: 1.02rem; line-height: 1.4;
             display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem; }
  .card .title { font-weight: 650; }
  .badges { display: inline-flex; gap: 0.4rem; align-items: center; flex: none; }
  .mag { font-weight: 600; font-size: 0.8rem; border: 1px solid var(--border-strong);
         border-radius: 0.35rem; padding: 0.05rem 0.45rem; color: var(--ink-2); }
  .alert { display: inline-flex; align-items: center; gap: 0.35em; font-weight: 600;
           font-size: 0.8rem; border: 1px solid var(--border-strong);
           border-radius: 999px; padding: 0.05rem 0.6rem; color: var(--ink); }
  .alert.Red::before { background: var(--critical); }
  .alert.Orange::before { background: var(--serious); }
  .alert.Green::before { background: var(--good); }
  .hazard { font-size: 0.72rem; letter-spacing: 0.08em; color: var(--ink-3);
            border: 1px solid var(--border); border-radius: 0.3rem;
            padding: 0.05rem 0.35rem; flex: none; }
  .meta { font-size: 0.82rem; color: var(--ink-2); margin: 0 0 0.2rem; }
  .meta a { color: var(--accent); text-decoration: none; }
  .meta a:hover { text-decoration: underline; }
  .card p { margin: 0.45rem 0 0; font-size: 0.92rem; color: var(--ink-2); }
  .banner { background: var(--warning-tint); color: var(--warning-ink);
            border: 1px solid var(--warning); border-left-width: 4px;
            border-radius: 0.5rem; padding: 0.65rem 1rem; margin: 0 0 0.8rem;
            font-size: 0.92rem; }
  .assess { border-left: 3px solid var(--accent); padding: 0.1rem 0 0.1rem 0.75rem;
            color: var(--ink); }
  .assess .priority { font-size: 0.7rem; text-transform: uppercase;
                      letter-spacing: 0.08em; font-weight: 700; color: var(--ink-3);
                      margin-right: 0.5em; }
  .lead { border: 1px solid var(--border); border-radius: 0.6rem;
          background: var(--surface-2); padding: 1rem 1.25rem; margin: 0 0 0.6rem; }
  .lead h2 { margin: 0 0 0.4rem; font-size: 1.15rem; line-height: 1.4; }
  .lead p { margin: 0; font-size: 0.98rem; color: var(--ink-2); }
  .quiet { font-size: 1rem; }
  footer { margin-top: 2.5rem; padding-top: 0.8rem; border-top: 1px solid var(--border);
           font-size: 0.78rem; color: var(--ink-3); }
  footer a { color: inherit; }
</style>
</head>
<body>
<header>
  <h1>HADR Situation Report</h1>
  <p class="sub">Global watch floor · USGS · GDACS · ReliefWeb</p>
  <p class="stamp">Data as of $stamp_utc UTC / $stamp_sgt SGT</p>
</header>
<div class="ops">$ops_chips</div>
$banners
$lead
<main>
$sections
</main>
<footer>Generated unattended by the
  <a href="https://github.com/mervo/hadr-claw">hadr-claw</a> agent ·
  feed health and change counts above reflect this run</footer>
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


def _card(e: Event, assessments: dict | None = None) -> str:
    alert = e.severity.get("gdacs_alert")
    badges = ""
    if alert in _ALERT_RANK:
        badges += f'<span class="alert {alert}">{alert}</span>'
    mag = e.severity.get("mag")
    if mag is not None:
        badges += f'<span class="mag">M {mag:.1f}</span>'
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
    assess_html = ""
    if assessments and e.uid in assessments:
        a = assessments[e.uid]
        assess_html = (
            f'<p class="assess"><span class="priority">{escape(a.get("priority") or "")}'
            f"</span>{escape(a['assessment'])}</p>"
        )
    return f"""<div class="card">
  <h3><span class="badges"><span class="hazard">{escape(e.hazard)}</span>{badges}</span>
      <span class="title">{escape(e.title)}</span></h3>
  <p class="meta">{escape(e.occurred_at)} · {place}{depth} · {links}</p>
  {assess_html}{summary_html}
</div>"""


def _section(title: str, events: list[Event], assessments: dict | None = None) -> str:
    if not events:
        return ""
    cards = "\n".join(_card(e, assessments) for e in sorted(events, key=_severity_key))
    return (
        f'<h2>{escape(title)} <span class="count">· {len(events)}</span></h2>\n{cards}'
    )


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

    chips = [
        f'<span class="chip {"ok" if s.ok else "bad"}">'
        f'{escape(s.feed)}: {"ok" if s.ok else "down"}'
        f'{f" · {s.latency_ms} ms" if s.latency_ms is not None else ""}</span>'
        for s in statuses
    ]
    chips.append(f'<span class="chip">{len(events)} significant event(s)</span>')
    if changes:
        chips.append(
            '<span class="chip">'
            + ", ".join(f"{v} {k}" for k, v in changes.counts().items() if k != "unchanged")
            + "</span>"
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

    if changes is None:
        sections = _section("Events", events, assessments)
    elif changes.quiet:
        since = f" since {escape(last_change_at)}" if last_change_at else ""
        sections = (
            f'<p class="stamp quiet">No new developments{since}. '
            f"{len(changes.unchanged)} event(s) remain under watch.</p>\n"
            + _section("Ongoing", changes.unchanged, assessments)
        )
    else:
        deleted_note = (
            '<div class="banner">Withdrawn by their feed while still current: '
            + ", ".join(escape(d.get("title") or d["uid"]) for d in changes.deleted)
            + "</div>"
            if changes.deleted
            else ""
        )
        sections = deleted_note + "\n".join(
            filter(None, [
                _section("Escalated", changes.escalated, assessments),
                _section("New", changes.new, assessments),
                _section("Updated", changes.updated, assessments),
                _section("Ongoing", changes.unchanged, assessments),
            ])
        )

    lead = ""
    if headline or overview:
        lead = '<div class="lead">'
        if headline:
            lead += f"<h2>{escape(headline)}</h2>"
        if overview:
            lead += f"<p>{escape(overview)}</p>"
        lead += "</div>"

    return PAGE.substitute(
        stamp_utc=stamp_utc, stamp_sgt=stamp_sgt, ops_chips="\n".join(chips),
        banners=banners, lead=lead, sections=sections,
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
