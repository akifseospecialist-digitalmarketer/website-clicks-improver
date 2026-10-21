# Changelog

## 1.0.0 - 2026-10-22

First release.

- `analyze_gsc.py`: reads page+query CSV/XLSX, GSC web-UI `.zip`/`.xlsx` exports (per-page filtered exports are mapped through the Filters tab) and separate Pages/Queries files. Flags low-CTR page-1 pages against an expected-CTR curve, lists page 2-3 pages, builds the page→query map and spots cannibalisation.
- `fetch_pages.py`: pulls title, meta description, canonical, robots, H1-H3, body text, word count and schema types. Falls back to manually gathered content (`--content-json`).
- `find_gaps.py`: per-query status (Missing / Partial / Scattered terms / Not in headings), intent detection, chunk clusters with placement, snippet checks and internal-link sources.
- `build_report.py`: 9-tab Excel working sheet with live formulas, priorities, status dropdowns and a markdown summary.
- `verify_workbook.py`: recalculates with LibreOffice and checks formula errors and title/meta lengths.
- Playbooks for CTR rewrites, page 2-3 push plans and content chunks.
- Fictional sample data and a finished sample report.
