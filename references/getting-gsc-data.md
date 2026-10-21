# Getting the right Google Search Console data

The skill works best with **page + query rows**: one row per page x query, with clicks, impressions, CTR and
position. That's what makes it possible to say "this page ranks for X but never mentions X".

Recommended date range: **last 3 months** (enough data, still current). Search type: **Web**.

## Option 1 - A GSC connector / MCP (fastest)
If Claude has a Search Console connector, it can pull `page` + `query` rows directly. Just give it the property
(e.g. `sc-domain:example.com`) and the date range.

## Option 2 - Search Analytics for Sheets (free Google Sheets add-on)
1. In Google Sheets: Extensions -> Add-ons -> install **Search Analytics for Sheets**.
2. Open it, choose your site, date range, search type Web.
3. **Group by: Page, Query.** Run.
4. File -> Download -> CSV. Upload that file.

## Option 3 - Looker Studio
1. Create a report with the **Search Console** connector, table type **URL Impression**.
2. Add a table with dimensions **Landing Page** + **Query** and metrics Clicks, Impressions, URL CTR, Average Position.
3. Export the table to CSV.

## Option 4 - The GSC web interface (no extra tools)
The normal export gives Queries and Pages *separately*. That's enough for low-CTR and page 2-3 analysis,
but not for keyword gaps. To get queries per page:
1. Performance -> Search results -> set the date range.
2. **+ Add filter -> Page -> Exact URL ->** paste the page URL.
3. Export -> Download CSV (a .zip) or Excel.
4. Repeat for each page you care about (start with the pages the skill flagged).
5. Upload all the files. Each export's Filters tab tells the skill which page its queries belong to.

The web interface shows at most 1,000 rows per table. Fine for most pages.

## Option 5 - GSC API / BigQuery bulk export
`searchanalytics.query` with `dimensions: ["page", "query"]`, `rowLimit: 25000`, paginating with `startRow`.
Or query the bulk-export tables in BigQuery. Export as CSV with columns `page, query, clicks, impressions, ctr, position`.

## Things to know
- **Use a single date range.** Exports made in GSC's *Compare* mode have doubled, date-prefixed columns and aren't supported.
- **Extra dimensions are fine.** If the file also has date, country or device columns, rows are summed per page + query.
- **Decimal commas are fine.** CSVs saved by Excel in European locales (`1.234`, `4,2`) are detected and converted.
- **Anonymised queries**: GSC hides rare queries for privacy, so page+query rows add up to less than the
  page totals. Upload the Pages export too if you want exact page totals.
- **Average position is an average** across all queries and impressions. Read the query list before judging a page.
- **Brand queries** inflate CTR. Tell the skill your brand names so they're excluded from gap analysis.
- Column names don't matter much: the skill recognises the common variants (Top pages, Landing Page, Query,
  Top queries, CTR, URL CTR, Position, Average position...).
