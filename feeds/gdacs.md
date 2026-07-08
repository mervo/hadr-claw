# GDACS

Global Disaster Alert and Coordination System (EU/UN). Multi-hazard: earthquakes,
cyclones, floods, volcanoes, drought, wildfires. Each event carries a colour-coded
alert level.

## Endpoint

GeoJSON event list (verified 6 Jul 2026):

    https://www.gdacs.org/gdacsapi/api/events/geteventlist/EVENTS4APP

RSS alternative: `https://www.gdacs.org/xml/rss.xml`. Per-event detail hangs off
`url.details` inside each feature.

## Example response (truncated)

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": { "type": "Point", "coordinates": [141.845, 40.4353] },
      "properties": {
        "eventtype": "EQ",
        "eventid": 1550421,
        "episodeid": 1716583,
        "glide": "",
        "name": "Earthquake in Japan",
        "htmldescription": "Green M 4.6 Earthquake in Japan at: 06 Jul 2026 11:29:36.",
        "alertlevel": "Green",
        "alertscore": 1,
        "episodealertlevel": "Green",
        "episodealertscore": 0.0,
        "istemporary": "false",
        "iscurrent": "true",
        "country": "Japan",
        "fromdate": "2026-07-06T11:29:36",
        "todate": "2026-07-06T11:29:36",
        "datemodified": "2026-07-06T12:09:48",
        "iso3": "JPN",
        "source": "NEIC",
        "url": {
          "report": "https://www.gdacs.org/report.aspx?eventid=1550421&episodeid=1716583&eventtype=EQ",
          "details": "https://www.gdacs.org/gdacsapi/api/events/geteventdata?eventtype=EQ&eventid=1550421"
        }
      }
    }
  ]
}
```

## Open questions

1. Every event carries `alertlevel`, `alertscore`, `episodealertlevel` and
   `episodealertscore`. Which of these is "the alert level" for reporting
   purposes — and can an event's colour change after you have already
   reported on it?
2. This event's `source` is `NEIC` — the same US agency behind the USGS feed.
   When the same physical earthquake arrives from two of your three feeds,
   what makes two records the same event?
3. GDACS publishes no rate limits and no uptime guarantees. What is a polite
   polling frequency, and what does your 08:30 report say on a morning the
   feed is down?
