# USGS Earthquakes

United States Geological Survey real-time earthquake feed. GeoJSON, regenerated
every minute, served as rolling windows.

## Endpoint

Verified 6 Jul 2026:

    https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson

Other windows and magnitude cut-offs exist (`all_hour`, `4.5_week`,
`significant_month`, …) — same shape throughout.

## Example response (truncated)

```json
{
  "type": "FeatureCollection",
  "metadata": {
    "generated": 1783342886000,
    "title": "USGS All Earthquakes, Past Day",
    "count": 208
  },
  "features": [
    {
      "type": "Feature",
      "properties": {
        "mag": 3.04,
        "place": "9 km NNE of Avalon, CA",
        "time": 1783342082180,
        "updated": 1783342799040,
        "felt": 1,
        "alert": null,
        "status": "automatic",
        "tsunami": 0,
        "sig": 143,
        "ids": ",ci41287863,us6000tafd,",
        "type": "earthquake",
        "title": "M 3.0 - 9 km NNE of Avalon, CA"
      },
      "geometry": { "type": "Point", "coordinates": [-118.3, 33.4, 12.1] },
      "id": "ci41287863"
    }
  ]
}
```

## Open questions

1. This event has one `id` but two entries in `ids`. Why would a single
   earthquake carry several identifiers, and which one do you store?
2. `status` is `"automatic"` and `updated` is later than `time`. Events get
   revised — magnitude, location, occasionally deleted outright. What happens
   to a report you have already published when its event changes underneath it?
3. `alert` is `null` here, but not always. What are its possible values, and
   how do they relate to GDACS's colours?
