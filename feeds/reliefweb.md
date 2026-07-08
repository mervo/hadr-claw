# ReliefWeb

UN OCHA's humanitarian information service. Curated and slower-moving than the
other two feeds: a "disaster" appears here once humans decide it matters.

## Endpoint

    https://api.reliefweb.int/v2/disasters?appname=<your-approved-appname>&preset=latest

Two things to know, both verified 6 Jul 2026:

- `v1` has been decommissioned; it returns HTTP 410.
- Since 1 November 2025 the API requires a **pre-approved** `appname`,
  requested via a form and confirmed by email:
  https://apidoc.reliefweb.int/parameters#appname

Without an approved appname:

```json
{
  "status": 403,
  "error": {
    "type": "AccessDeniedHttpException",
    "message": "You are not using an approved appname. Kindly request an appname from ReliefWeb here: https://apidoc.reliefweb.int/parameters#appname"
  }
}
```

The RSS feed needs no approval:

    https://reliefweb.int/disasters/rss.xml

## Example response (truncated, from the RSS feed)

```xml
<item>
  <title>Venezuela: Earthquakes - Jun 2026</title>
  <link>https://reliefweb.int/disaster/eq-2026-000093-ven</link>
  <pubDate>Wed, 24 Jun 2026 00:00:00 +0000</pubDate>
  <description>
    &lt;div class="tag country"&gt;Affected country: Venezuela (Bolivarian Republic of)&lt;/div&gt;
    &lt;div class="tag glide"&gt;Glide: EQ-2026-000093-VEN&lt;/div&gt;
    &lt;p&gt;On 24 June 2026, two strong earthquakes, preliminarily measured at
    magnitudes 7.1 and 7.5, struck north-central Venezuela in rapid
    succession, with epicentres near Morón, Carabobo State. ...&lt;/p&gt;
  </description>
</item>
```

## Open questions

1. The appname review takes time you may not have this week. What do you
   build against in the meantime, and what does the RSS feed lack that the
   API would give you?
   > **Answered (Tier 2):** we build against the RSS feed (`hadr/feeds/reliefweb.py`);
   > the JSON API can slot in behind the same `normalize()` contract once the
   > appname is approved (request form: https://apidoc.reliefweb.int/parameters#appname —
   > still to be filed). RSS lacks: coordinates (so spatio-temporal dedup can't
   > apply — only GLIDE ties these records to other feeds), structured
   > country/type/status fields, and real update timestamps (`pubDate` is the
   > creation date at midnight; change detection must fingerprint the
   > description text instead).
2. This Venezuela entry describes earthquakes that GDACS and USGS reported
   days earlier, under different identifiers. Is there anything in this
   record that could tie the three feeds together?
   > **Answered (Tier 2):** the **GLIDE number**, present in both the
   > description tag and the link slug. The parser prefers the description and
   > falls back to the slug (`hadr/feeds/reliefweb.py::_glide`); the test suite
   > asserts the two agree on fixtures, but the runtime does not cross-validate.
   > GDACS carries the same GLIDE on its Orange/Red events, which merges the
   > two; USGS joins the cluster via GDACS through spatio-temporal matching.
   > Exactly this trio is the `tests/fixtures/crossfeed/` fixture verified by
   > `scripts/check_dedup.py`.
3. The API docs say usage is monitored and adapted per application. What are
   the actual limits, and how should your agent behave when it hits one?
   > **Partially answered (Tier 2):** moot while on RSS (one fetch per run).
   > When the API lands: the documented ceiling is 1000 calls/day per appname;
   > on 429 the agent should fall back to RSS for that run and note the
   > degradation on the dashboard, same as any feed failure.
