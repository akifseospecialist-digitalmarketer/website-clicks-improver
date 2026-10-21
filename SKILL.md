---
name: website-clicks-improver
description: Turns Google Search Console (GSC) data into more clicks. Finds low-CTR pages on Google page 1 and writes better titles and meta descriptions; finds pages stuck on Google page 2-3 and builds a push-to-page-1 plan; finds keywords a page already ranks for but does not use in its content and writes ready-to-paste content chunks for them. Delivers an Excel working sheet. Use whenever someone shares a GSC / Search Console export or asks to improve CTR, get more clicks from Google, find low-CTR pages, find page 2 or page 3 keywords, striking-distance keywords, "keywords we rank for but don't use", keyword gaps on existing pages, or content to add to existing pages.
---

# Website Clicks Improver

Three jobs, one workbook:

| # | Finds | Delivers |
|---|---|---|
| A | **Low-CTR pages**: avg position < 11 but CTR well below what that position should earn | Diagnosis, 2 title options, 2 meta options, other snippet fixes |
| B | **Page 2-3 pages**: avg position 11-30 | A push-to-page-1 plan + internal links to add |
| C | **Keyword gaps**: queries a page ranks for that its content doesn't use (or only partly uses) | Ready-to-paste **content chunks**, each with a placement on the page |

Work through the steps in order. Scripts live in this skill's `scripts/` folder (Python 3.9+, `pandas openpyxl requests
beautifulsoup4`; install any that are missing). The skill folder may be read-only, so **work from a writable folder**
and call the scripts by their full path:

```bash
SKILL_DIR=/path/to/website-clicks-improver   # the folder this SKILL.md is in
mkdir -p work outputs                          # in a writable working directory
```

Use `python3` (or `python` if that's what the environment has).

---

## Step 0 - Get the right data

**Best input: page + query rows** (each row = one page x one query, with clicks, impressions, CTR, position).
Without it you can still do A and B, but C (keyword gaps per page) needs it.

In order of preference:
1. **A GSC connector / MCP is available** -> pull it yourself: search type `web`, dimensions `page` + `query`,
   last 3 months (or what the user asks), row limit 25,000. Save as CSV with columns
   `page,query,clicks,impressions,ctr,position`. Also pull dimension `page` alone (exact page totals).
2. **The user uploads files**: accept anything. Page+query CSV/XLSX, the GSC web-UI `.zip` / `.xlsx` export,
   or separate Pages/Queries files. UI exports filtered to one page are mapped to that page automatically
   (via the Filters tab), so several per-page exports work too.
3. **Only a plain UI export (Queries + Pages, unfiltered)** -> run steps 1-2 anyway, deliver A and B, and tell the
   user how to get page+query data for C (see `references/getting-gsc-data.md`), naming the exact pages to export.

Also ask for (don't block on it - use sensible defaults and `[placeholders]`):
- the site URL and **brand name(s)** (brand queries are excluded from gap analysis)
- the language variant to write in (e.g. Australian English) - default: match the site's own copy
- business facts chunks may need: price ranges, years in business, service areas, guarantees

## Step 1 - Analyse the GSC data

```bash
python3 "$SKILL_DIR"/scripts/analyze_gsc.py <files...> -o work/analysis.json --site https://example.com \
  --brand "acme,acme plumbing" --date-range "1 Jul - 30 Sep 2026"
```

Useful flags: `--min-impr 100` (low-CTR list), `--min-impr-p23 50`, `--min-pair-impr 10`,
`--ctr-threshold 0.7` (flag when CTR < 70% of expected), `--top 25` (pages per list), `--benchmark site`
(use the site's own CTR-by-position instead of the industry curve - better for big sites, 100+ pages).

Small site with few rows? Lower the thresholds (e.g. `--min-impr 30 --min-impr-p23 20 --min-pair-impr 5`;
find_gaps.py picks up `--min-pair-impr` automatically). Huge site? Raise them, and raise `--top` if the user wants
more than 25 pages per list. Only the `pages_to_fetch` pages go into the workbook.
Read the printed warnings (number format converted, extra dimensions summed, relative URLs, nothing qualified...)
and pass them on to the user if they matter.

## Step 2 - Get the content of each focus page

```bash
python3 "$SKILL_DIR"/scripts/fetch_pages.py work/analysis.json -o work/pages.json
```

If the sandbox blocks outbound requests, the first page fails fast; if requests hang instead, add `--timeout 8`.
For pages that failed: fetch each URL in `pages_to_fetch` with your web-fetch tool, write
`work/manual_content.json` keyed by those exact URLs, in the format shown in the script's docstring (title,
meta_description, h1, headings as `[["h2", "text"], ...]`, body_text), then re-run with
`--content-json work/manual_content.json --no-fetch`. If the title or meta can't be captured, leave them empty and say
so in the diagnosis rather than guessing. As a last resort ask the user to paste the page copy.

## Step 3 - Find keyword gaps

```bash
python3 "$SKILL_DIR"/scripts/find_gaps.py work/analysis.json work/pages.json -o work/gaps.json
```

Per page this gives `snippet_checks` (title/meta faults), `gaps` (query-level status), `clusters` (gap queries
grouped into one chunk each, with intent, chunk type and placement) and `link_sources` (internal links to add).

## Step 4 - Write the suggestions (this is where judgement matters)

Read these first. They hold the rules and patterns that make the output good:
- `references/ctr-playbook.md` - diagnosing low CTR + title/meta formulas by intent
- `references/page-2-3-playbook.md` - what actually moves a page from 11-30 onto page 1
- `references/content-chunk-guide.md` - chunk templates, placement and the anti-stuffing rules

Then, using `analysis.json`, `pages.json` and `gaps.json`:

Write suggestions for every low-CTR and page 2-3 page **in `pages_to_fetch`** (the rest aren't in the workbook).

1. **Every low-CTR page**: a one or two sentence diagnosis tied to the evidence (snippet checks + query list),
   2 title options, 2 meta options, and other fixes (H1, schema, SERP-feature notes).
   If `snippet_checks` says "no obvious fault", look at the live SERP for the top query with web search if you
   can (AI Overview, featured snippet, local pack, ads, a rewritten title) and say what you found.
2. **Every page 2-3 page**: diagnosis + a push plan of 3-6 specific, ordered actions (optionally a
   `title_options` / `h1_suggestion`, shown in the tab). Reference the actual chunk
   IDs and link sources. If you can search, compare against the top 3 results for the main query
   (depth, subtopics, format) and name what they cover that the page doesn't.
3. **Every cluster in gaps.json**: write the chunk. One chunk per cluster, in the chunk type and placement given
   (you may improve the placement). Check cannibalisation first: if another page clearly owns that query
   (e.g. a dedicated cost page), write a short teaser + link to that page instead of a competing section.

Save as `work/suggestions.json`:

```json
{
  "site_name": "Acme Plumbing",
  "pages": {
    "https://example.com/page/": {
      "diagnosis": "Why CTR is low / why the page is stuck - cite the evidence.",
      "title_options": ["Recommended title (<= 60 chars)", "Alternative"],
      "meta_options": ["Recommended meta (140-155 chars)", "Alternative"],
      "h1_suggestion": "optional",
      "other_fixes": ["optional snippet / schema / SERP fixes"],
      "actions": ["page 2-3 push plan, step 1", "step 2"],
      "internal_links": [{"source": "https://example.com/other/", "anchor": "text", "why": "reason"}]
    }
  },
  "chunks": [
    {"url": "https://example.com/page/", "cluster": "C1", "keywords": ["query a", "query b"],
     "chunk_type": "FAQ", "placement": "New FAQ section before 'Book now'",
     "heading": "H2/H3 text (blank for sentence edits)",
     "content": "The ready-to-paste text. Use \n for line breaks, '- ' for bullets, 'Q: / A:' for FAQs, and '| a | b |' rows for tables.",
     "notes": "Facts to confirm before publishing, e.g. [price]"}
  ]
}
```

Each chunk's `cluster` must be the cluster ID from gaps.json (C1, C2... per page). For an extra chunk that
isn't tied to a cluster, give it its own ID such as `X1`.

Hard rules:
- Titles <= 60 characters; metas 140-155 (never under 70 or over 160). Count them.
- Never invent facts: prices, stats, years, awards, guarantees. Use `[placeholder]` and list it in `notes`.
- Each target keyword appears once in its chunk, in a natural sentence. No stuffing, no keyword lists.
- Never write "near me" into copy. Use the real suburb/city names instead.
- Match the site's voice and language variant. Write for the reader first.

## Step 5 - Build the workbook

```bash
python3 "$SKILL_DIR"/scripts/build_report.py --analysis work/analysis.json --pages work/pages.json --gaps work/gaps.json \
  --suggestions work/suggestions.json -o "outputs/<domain>-clicks-improver-<YYYY-MM-DD>.xlsx" --md outputs/summary.md
```

Tabs: Summary, Low CTR Pages, Page 2-3 Pages, Keyword Gaps, Content Chunks, Internal Links, Cannibalisation
(only if found), Action Plan, Method & Notes. Totals, CTRs, char counts and click estimates are live formulas.

## Step 6 - Verify

```bash
python3 "$SKILL_DIR"/scripts/verify_workbook.py outputs/<file>.xlsx
```

It must print `RESULT: PASS` (no formula errors, recommended and alternative titles <= 60, metas 70-160). Fix and
rebuild on FAIL. "Recalculation failed" is a FAIL: just run verify again.
Warnings about unwritten chunks mean you skipped clusters - write them unless the user asked for a subset.

## Step 7 - Deliver

Send the workbook. In the reply keep it short:
- the total click opportunity (low-CTR extra clicks + page 2-3 clicks at position 5) and the period it covers
- the top 3 actions, each in one line
- anything the user must confirm (every `[placeholder]`), and any data limitation (e.g. no page+query data)

End the summary with: *Built with website-clicks-improver by Akif Qureshi | SEO Specialist - algoblueprints.com*

---

## Fallbacks

| Problem | Do this |
|---|---|
| GSC "Compare" mode export | Ask for a normal (single date range) export; compare-mode columns aren't supported |
| No page+query data | Deliver A + B; for C list the top pages and explain how to export their queries (`references/getting-gsc-data.md`) |
| Pages can't be fetched | Web-fetch tool -> `--content-json`; else ask the user to paste the copy |
| Very few rows / tiny site | Lower `--min-impr`, `--min-impr-p23`, `--min-pair-impr` and re-run |
| Brand pages dominate | Pass `--brand`; brand queries are excluded from gaps and cannibalisation |
| User wants one page only | Run everything, then keep that URL only when writing suggestions |
| No Python available | Do the same analysis by hand following this file and the playbooks; deliver a table instead of the workbook |
