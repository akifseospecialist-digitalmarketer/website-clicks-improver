#!/usr/bin/env python3
"""
analyze_gsc.py - Step 1 of the website-clicks-improver skill.

Reads Google Search Console (GSC) data and finds:

  A) Low-CTR pages   - pages on Google page 1 (avg position < 11) whose CTR is well
                       below the expected CTR for their position.
  B) Page 2-3 pages  - avg position 11 to 30.99: close enough to push onto page 1.
  C) Page -> query map (when page+query data is available), used by find_gaps.py.
  D) Cannibalisation watch - queries where two or more of your pages split impressions.

Accepted inputs (one or more files, mix freely):
  * page+query CSV/XLSX (best) - columns like page, query, clicks, impressions, ctr, position.
    Sources: Search Analytics for Sheets, Looker Studio, the GSC API, a GSC MCP connector.
  * GSC web-UI export (.zip or .xlsx with Queries / Pages / Filters tabs). If the export was
    filtered to one page, its queries are mapped to that page automatically.
  * Separate Pages.csv / Queries.csv files.

Usage:
  python analyze_gsc.py INPUT [INPUT ...] -o work/analysis.json
         [--site https://example.com] [--brand "acme,acme co"]
         [--min-impr 100] [--min-impr-p23 50] [--min-pair-impr 10]
         [--ctr-threshold 0.7] [--top 25] [--benchmark industry|site] [--ctr-curve curve.json]
         [--date-range "1 Jul - 30 Sep 2026"]
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import zipfile
from pathlib import Path

import pandas as pd

# --------------------------------------------------------------------------------------
# Expected organic CTR by position (non-brand, all devices).
# Deliberately conservative: blended from public CTR studies and adjusted down for the
# AI Overviews era. Override with --ctr-curve or use --benchmark site.
# --------------------------------------------------------------------------------------
DEFAULT_CTR_CURVE = {
    1: 0.25, 2: 0.15, 3: 0.10, 4: 0.07, 5: 0.055, 6: 0.040, 7: 0.032, 8: 0.026,
    9: 0.022, 10: 0.019, 11: 0.012, 12: 0.011, 13: 0.010, 14: 0.009, 15: 0.008,
    20: 0.006, 25: 0.004, 30: 0.003, 50: 0.002, 100: 0.001,
}

COLUMN_ALIASES = {
    "page": {"page", "pages", "top pages", "landing page", "landing page url", "url", "page url",
             "address", "landingpage", "pageurl"},
    "query": {"query", "queries", "top queries", "search query", "keyword", "keywords",
              "search term", "searchquery"},
    "clicks": {"clicks", "url clicks", "click"},
    "impressions": {"impressions", "impr", "impression", "url impressions"},
    "ctr": {"ctr", "url ctr", "site ctr", "click through rate", "clickthrough rate"},
    "position": {"position", "average position", "avg position", "avg pos", "average pos",
                 "avg. position", "url position", "pos", "rank"},
}

FILTER_COLS = {"filter", "filters"}


def norm_header(h: str) -> str:
    h = str(h).strip().lower().replace("﻿", "")
    h = re.sub(r"[^a-z0-9 ]+", " ", h)
    return re.sub(r"\s+", " ", h).strip()


def map_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename = {}
    for col in df.columns:
        n = norm_header(col)
        for target, aliases in COLUMN_ALIASES.items():
            if n in {norm_header(a) for a in aliases} and target not in rename.values():
                rename[col] = target
                break
    return df.rename(columns=rename)


EURO_DECIMAL = re.compile(r"^-?\d+,\d{1,2}%?$")              # 4,2  2,7%  (can't be US thousands)
EURO_THOUSANDS = re.compile(r"^\d{1,3}(\.\d{3})+(,\d+)?$")  # 1.234  45.678,5


def is_european(df: pd.DataFrame, cols: list[str]) -> bool:
    """True when the numbers use a decimal comma (e.g. a CSV saved by Excel in a European locale):
    a decimal comma anywhere (4,2 / 2,7%), or dot-grouped thousands in clicks/impressions,
    which are always whole numbers (1.234)."""
    for c in cols:
        if c in df.columns and not pd.api.types.is_numeric_dtype(df[c]):
            vals = df[c].dropna().astype(str).str.strip().head(500)
            if vals.str.match(EURO_DECIMAL).any():
                return True
            if c in ("clicks", "impressions") and vals.str.match(EURO_THOUSANDS).any():
                return True
    return False


def to_number(s: pd.Series, european: bool = False) -> pd.Series:
    if not pd.api.types.is_numeric_dtype(s):  # object or pandas>=3 "str" dtype
        s = s.astype(str).str.replace("%", "", regex=False).str.strip()
        if european:
            s = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
        else:
            s = s.str.replace(",", "", regex=False)
        s = s.replace({"": None, "nan": None, "None": None, "-": None})
    return pd.to_numeric(s, errors="coerce")


class InputError(ValueError):
    pass


def clean_table(df: pd.DataFrame, source: str = "", warnings: list | None = None) -> pd.DataFrame:
    df = map_columns(df)
    cols = {norm_header(c): c for c in df.columns}
    if "position" not in df.columns and "sum top position" in cols and "impressions" in df.columns:
        # BigQuery bulk export: sum_top_position is zero-based and summed over impressions
        df["position"] = to_number(df[cols["sum top position"]]) / to_number(df["impressions"]) + 1
    missing = [c for c in ("clicks", "impressions", "position") if c not in df.columns]
    if missing:
        raise InputError(f"{source}: missing column(s) {', '.join(missing)}. Found: {', '.join(map(str, df.columns))}. "
                         "Export Clicks, Impressions and Position from GSC (CTR is optional).")
    euro = is_european(df, ["clicks", "impressions", "position", "ctr"])
    if euro and warnings is not None:
        warnings.append(f"{source}: decimal-comma number format detected (e.g. 4,2) and converted.")
    for c in ("clicks", "impressions", "position"):
        if c in df.columns:
            df[c] = to_number(df[c], euro)
    if "clicks" in df.columns:
        df["clicks"] = df["clicks"].fillna(0)
    if "impressions" in df.columns:
        df = df[df["impressions"].fillna(0) > 0].copy()
    if {"clicks", "impressions"} <= set(df.columns):
        # Recompute CTR: more precise than the rounded value in exports.
        df["ctr"] = df["clicks"] / df["impressions"]
    elif "ctr" in df.columns:
        raw = df["ctr"].astype(str)
        had_pct = raw.str.contains("%").any()
        df["ctr"] = to_number(df["ctr"], euro)
        if had_pct or df["ctr"].max() > 1:
            df["ctr"] = df["ctr"] / 100
    for c in ("page", "query"):
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()
            df = df[(df[c] != "") & (df[c].str.lower() != "nan")]
    return df


DIMENSION_HINTS = {"date", "dates", "country", "countries", "device", "devices", "search appearance",
                   "search type", "month", "week", "day"}


def collapse(df: pd.DataFrame, keys: list[str], source: str, warnings: list) -> pd.DataFrame:
    """Sum rows that share the same page/query (e.g. one row per date, country or device)."""
    extra = [c for c in df.columns if norm_header(c) in DIMENSION_HINTS]
    if not df.duplicated(subset=keys).any():
        return df
    if extra:
        warnings.append(f"{source}: extra dimension column(s) {', '.join(map(str, extra))} found - rows were summed per "
                        f"{' + '.join(keys)}.")
    else:
        warnings.append(f"{source}: duplicate {' + '.join(keys)} rows were summed.")
    g = (df.assign(_w=df["position"] * df["impressions"])
         .groupby(keys, as_index=False)
         .agg(clicks=("clicks", "sum"), impressions=("impressions", "sum"), _w=("_w", "sum")))
    g["position"] = g["_w"] / g["impressions"]
    g["ctr"] = g["clicks"] / g["impressions"]
    return g.drop(columns="_w")


def classify(df: pd.DataFrame) -> str:
    cols = {norm_header(c) for c in df.columns}
    if cols & FILTER_COLS and "value" in cols:
        return "filters"
    m = set(map_columns(df.copy()).columns)
    if "impressions" not in m:
        return "other"
    if {"page", "query"} <= m:
        return "pairs"
    if "page" in m:
        return "pages"
    if "query" in m:
        return "queries"
    return "other"


def read_csv_bytes(data: bytes) -> pd.DataFrame:
    for enc in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            # read as text: number formats (1,234 vs 1.234 vs 4,2) are decided later in to_number()
            return pd.read_csv(io.BytesIO(data), encoding=enc, sep=None, engine="python", dtype=str,
                               keep_default_na=False)
        except Exception:
            continue
    raise ValueError("Could not parse CSV")


def page_from_filters(fdf: pd.DataFrame) -> str | None:
    """GSC exports include a Filters tab. If a Page filter was applied, return its URL."""
    cols = {norm_header(c): c for c in fdf.columns}
    fcol = cols.get("filter") or cols.get("filters")
    vcol = cols.get("value")
    if not fcol or not vcol:
        return None
    for _, row in fdf.iterrows():
        if str(row[fcol]).strip().lower().startswith("page"):
            m = re.search(r"https?://\S+", str(row[vcol]))
            if m:
                return m.group(0).rstrip(",;")
    return None


def date_from_filters(fdf: pd.DataFrame) -> str | None:
    cols = {norm_header(c): c for c in fdf.columns}
    fcol = cols.get("filter") or cols.get("filters")
    vcol = cols.get("value")
    if not fcol or not vcol:
        return None
    for _, row in fdf.iterrows():
        if str(row[fcol]).strip().lower().startswith("date"):
            return str(row[vcol]).strip()
    return None


def load_bundle(tables: dict[str, pd.DataFrame], source: str, store: dict) -> None:
    """A bundle = tables from one export (zip / multi-sheet xlsx / single csv)."""
    kinds = {name: classify(df) for name, df in tables.items()}
    filt_page = None
    for name, kind in kinds.items():
        if kind == "filters":
            filt_page = page_from_filters(tables[name])
            d = date_from_filters(tables[name])
            if d:
                store["date_ranges"].add(d)
    for name, kind in kinds.items():
        df = tables[name]
        src = f"{source} [{name}]"
        W = store["warnings"]
        if kind == "pairs":
            store["pairs"].append(collapse(clean_table(df, src, W), ["page", "query"], src, W))
            store["log"].append(f"{src}: page+query rows = {len(df)}")
        elif kind == "queries":
            q = collapse(clean_table(df, src, W), ["query"], src, W)
            if filt_page:
                q = q.assign(page=filt_page)
                store["pairs"].append(q)
                store["log"].append(f"{source} [{name}]: {len(q)} queries mapped to filtered page {filt_page}")
            else:
                store["queries"].append(q)
                store["log"].append(f"{source} [{name}]: site queries = {len(q)}")
        elif kind == "pages":
            p = collapse(clean_table(df, src, W), ["page"], src, W)
            store["pages"].append(p.assign(_filtered=bool(filt_page)))
            store["log"].append(f"{src}: pages = {len(p)}")


def load_input(path: Path, store: dict) -> None:
    suffix = path.suffix.lower()
    if suffix == ".zip":
        tables = {}
        with zipfile.ZipFile(path) as z:
            for member in z.namelist():
                if member.lower().endswith(".csv"):
                    try:
                        tables[Path(member).stem] = read_csv_bytes(z.read(member))
                    except Exception as e:  # noqa: BLE001
                        store["warnings"].append(f"Skipped {member} in {path.name}: {e}")
                elif member.lower().endswith((".xlsx", ".xls")):
                    sheets = pd.read_excel(io.BytesIO(z.read(member)), sheet_name=None)
                    tables.update(sheets)
        load_bundle(tables, path.name, store)
    elif suffix in (".xlsx", ".xlsm", ".xls"):
        load_bundle(pd.read_excel(path, sheet_name=None), path.name, store)
    elif suffix in (".csv", ".tsv", ".txt"):
        load_bundle({path.stem: read_csv_bytes(path.read_bytes())}, path.name, store)
    elif path.is_dir():
        for child in sorted(path.iterdir()):
            if child.suffix.lower() in (".zip", ".xlsx", ".xls", ".csv", ".tsv"):
                load_input(child, store)
    else:
        store["warnings"].append(f"Unsupported file type: {path}")


# --------------------------------------------------------------------------------------
# Benchmarks
# --------------------------------------------------------------------------------------
def make_curve_fn(curve: dict[int, float]):
    pts = sorted((float(k), float(v)) for k, v in curve.items())

    def fn(pos: float) -> float:
        if pos is None or pd.isna(pos):
            return float("nan")
        if pos <= pts[0][0]:
            return pts[0][1]
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            if x1 <= pos <= x2:
                return y1 + (y2 - y1) * (pos - x1) / (x2 - x1)
        return pts[-1][1]

    return fn


def site_curve(pages: pd.DataFrame, industry: dict[int, float], min_rows: int = 8) -> dict[int, float]:
    """Site's own median CTR per rounded position (1-10); falls back to the industry curve."""
    curve = dict(industry)
    df = pages[(pages["position"] < 10.5) & (pages["impressions"] >= 50)].copy()
    df["bucket"] = df["position"].round().clip(lower=1).astype(int)
    for b, g in df.groupby("bucket"):
        if len(g) >= min_rows:
            curve[int(b)] = float(g["ctr"].median())
    return curve


def is_brand(q: str, brand_terms: list[str]) -> bool:
    ql = q.lower()
    return any(b and re.search(rf"(?<![a-z0-9]){re.escape(b)}(?![a-z0-9])", ql) for b in brand_terms)


def tertile_labels(values: pd.Series) -> pd.Series:
    if len(values) == 0:
        return pd.Series(dtype=str)
    if len(values) < 3:
        return pd.Series(["High"] * len(values), index=values.index)
    hi, lo = values.quantile(0.67), values.quantile(0.33)
    return values.apply(lambda v: "High" if v >= hi else ("Medium" if v >= lo else "Low"))


def absolutise(url: str, site: str | None) -> str:
    if site and not re.match(r"https?://", url):
        return site.rstrip("/") + "/" + url.lstrip("/")
    return url


# --------------------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("work/analysis.json"))
    ap.add_argument("--site", help="Site root, used to absolutise relative URLs")
    ap.add_argument("--brand", default="", help="Comma-separated brand terms (excluded from gap/cannibalisation analysis)")
    ap.add_argument("--min-impr", type=int, default=100, help="Min page impressions for the low-CTR list")
    ap.add_argument("--min-impr-p23", type=int, default=50, help="Min page impressions for the page 2-3 list")
    ap.add_argument("--min-pair-impr", type=int, default=10, help="Min impressions for a page+query row to count")
    ap.add_argument("--ctr-threshold", type=float, default=0.7, help="Flag when CTR < threshold x expected CTR")
    ap.add_argument("--top", type=int, default=25, help="Max pages per list to pass on for fetching")
    ap.add_argument("--benchmark", choices=["industry", "site"], default="industry")
    ap.add_argument("--ctr-curve", type=Path, help='JSON like {"1": 0.28, "2": 0.16, ...}')
    ap.add_argument("--date-range", help='Date range of the data, e.g. "1 Jul - 30 Sep 2026" (shown in the report)')
    args = ap.parse_args()

    store = {"pairs": [], "pages": [], "queries": [], "log": [], "warnings": [], "date_ranges": set()}
    for p in args.inputs:
        if not p.exists():
            sys.exit(f"Input not found: {p}")
        try:
            load_input(p, store)
        except InputError as e:
            sys.exit(f"ERROR: {e}")

    brand_terms = [b.strip().lower() for b in args.brand.split(",") if b.strip()]

    # Relative URLs (e.g. "/widgets/") need a site root. Use --site, else infer it from absolute URLs.
    all_urls = [u for df in store["pairs"] + store["pages"] for u in df["page"].astype(str)]
    if not args.site and any(not re.match(r"https?://", u) for u in all_urls):
        roots = pd.Series([re.match(r"(https?://[^/]+)", u).group(1) for u in all_urls if re.match(r"https?://", u)])
        if len(roots):
            args.site = roots.mode()[0]
            store["warnings"].append(f"Relative URLs found - used {args.site} as the site root (pass --site to change).")
        else:
            store["warnings"].append("Relative URLs found and no --site given - pages can't be fetched. Re-run with --site.")

    pairs = pd.concat(store["pairs"], ignore_index=True) if store["pairs"] else pd.DataFrame()
    if not pairs.empty:
        pairs["page"] = pairs["page"].apply(lambda u: absolutise(u, args.site))
        pairs = collapse(pairs, ["page", "query"], "combined inputs", store["warnings"])
        pairs["is_brand"] = pairs["query"].apply(lambda q: is_brand(q, brand_terms))

    # ---- Page-level table -------------------------------------------------------------
    pages = pd.DataFrame()
    if store["pages"]:
        pages = pd.concat(store["pages"], ignore_index=True)
        pages["page"] = pages["page"].apply(lambda u: absolutise(u, args.site))
        # the same page may come from several exports (e.g. per-page filtered ones): keep the fullest row
        pages = pages.sort_values("impressions", ascending=False).drop_duplicates("page")
        pages = pages.drop(columns=[c for c in pages.columns if c.startswith("_")])
        pages["source"] = "GSC pages report"
    if not pairs.empty:
        agg = (pairs.assign(_w=pairs["position"] * pairs["impressions"])
               .groupby("page", as_index=False)
               .agg(clicks=("clicks", "sum"), impressions=("impressions", "sum"), _w=("_w", "sum")))
        agg["position"] = agg["_w"] / agg["impressions"]
        agg = agg.drop(columns="_w")
        agg["ctr"] = agg["clicks"] / agg["impressions"]
        agg["source"] = "aggregated from page+query rows"
        missing = agg[~agg["page"].isin(pages["page"])] if not pages.empty else agg
        pages = pd.concat([pages, missing], ignore_index=True) if not pages.empty else missing
    if pages.empty:
        sys.exit("No page-level data found. Provide a Pages export or page+query rows.")
    pages = pages[["page", "clicks", "impressions", "ctr", "position", "source"]].copy()

    data_mode = "page+query" if not pairs.empty else ("pages+queries (unmapped)" if store["queries"] else "pages only")
    if data_mode != "page+query":
        store["warnings"].append(
            "No page+query data: keyword gaps per page cannot be mapped. See references/getting-gsc-data.md "
            "for how to export queries per page.")
    if (pages["source"] == "aggregated from page+query rows").all():
        store["warnings"].append(
            "Page totals were aggregated from page+query rows. GSC hides anonymised queries, so these totals "
            "under-count real page clicks/impressions; add the Pages export for exact totals.")

    # ---- Benchmarks -------------------------------------------------------------------
    industry = DEFAULT_CTR_CURVE
    if args.ctr_curve:
        industry = {int(k): float(v) for k, v in json.loads(args.ctr_curve.read_text()).items()}
    curve = site_curve(pages, industry) if args.benchmark == "site" else industry
    if args.benchmark == "site" and curve == industry:
        store["warnings"].append("--benchmark site: no position had 8+ pages with 50+ impressions, so the industry curve was used.")
    bad = pages[(pages["clicks"] > pages["impressions"]) | (pages["position"] > 150)]
    if len(bad):
        store["warnings"].append(f"{len(bad)} page row(s) have clicks > impressions or position > 150 - check the number format.")
    exp = make_curve_fn(curve)
    pages["expected_ctr"] = pages["position"].apply(exp)
    pages["ctr_ratio"] = pages["ctr"] / pages["expected_ctr"]

    # ---- A) Low CTR (page 1) ----------------------------------------------------------
    low = pages[(pages["position"] < 11) & (pages["impressions"] >= args.min_impr)
                & (pages["ctr"] < args.ctr_threshold * pages["expected_ctr"])].copy()
    low["extra_clicks"] = (low["impressions"] * low["expected_ctr"] - low["clicks"]).clip(lower=0).round()
    low = low.sort_values("extra_clicks", ascending=False)
    low["priority"] = tertile_labels(low["extra_clicks"])

    # ---- B) Page 2-3 ------------------------------------------------------------------
    p23 = pages[(pages["position"] >= 11) & (pages["position"] < 31)
                & (pages["impressions"] >= args.min_impr_p23)].copy()
    p23["serp_page"] = p23["position"].apply(lambda p: 2 if p < 21 else 3)
    ctr5 = exp(5)
    p23["clicks_at_pos5"] = (p23["impressions"] * ctr5 - p23["clicks"]).clip(lower=0).round()
    p23 = p23.sort_values("clicks_at_pos5", ascending=False)
    p23["priority"] = tertile_labels(p23["clicks_at_pos5"])

    if low.empty and p23.empty:
        store["warnings"].append("No pages qualified. On a small site lower the thresholds, e.g. "
                                 "--min-impr 30 --min-impr-p23 20 --min-pair-impr 5.")

    # ---- C) Page -> queries -----------------------------------------------------------
    focus = list(dict.fromkeys(list(low["page"].head(args.top)) + list(p23["page"].head(args.top))))
    page_queries: dict[str, list] = {}
    if not pairs.empty:
        pq = pairs[pairs["impressions"] >= args.min_pair_impr]
        for url in focus:
            g = pq[pq["page"] == url].sort_values("impressions", ascending=False).head(60)
            page_queries[url] = [
                {"query": r.query, "clicks": int(r.clicks), "impressions": int(r.impressions),
                 "ctr": round(float(r.ctr), 4), "position": round(float(r.position), 1),
                 "is_brand": bool(r.is_brand)}
                for r in g.itertuples()
            ]

    # ---- D) Cannibalisation -----------------------------------------------------------
    cannibal = []
    if not pairs.empty:
        nb = pairs[(~pairs["is_brand"]) & (pairs["impressions"] >= args.min_pair_impr)]
        for q, g in nb.groupby("query"):
            if g["page"].nunique() < 2:
                continue
            g = g.sort_values("impressions", ascending=False)
            total = g["impressions"].sum()
            if g.iloc[1]["impressions"] / total < 0.2:
                continue
            cannibal.append({
                "query": q, "total_impressions": int(total),
                "pages": [{"page": r.page, "impressions": int(r.impressions), "clicks": int(r.clicks),
                           "position": round(float(r.position), 1)} for r in g.head(5).itertuples()],
            })
        cannibal.sort(key=lambda c: c["total_impressions"], reverse=True)
        cannibal = cannibal[:50]

    def rows(df: pd.DataFrame, extra: list[str]) -> list[dict]:
        out = []
        for r in df.to_dict("records"):
            d = {"page": r["page"], "clicks": int(r["clicks"]), "impressions": int(r["impressions"]),
                 "ctr": round(float(r["ctr"]), 4), "position": round(float(r["position"]), 1),
                 "expected_ctr": round(float(r["expected_ctr"]), 4)}
            for k in extra:
                v = r[k]
                d[k] = int(v) if isinstance(v, float) and v.is_integer() else v
            out.append(d)
        return out

    tot_clicks, tot_impr = float(pages["clicks"].sum()), float(pages["impressions"].sum())
    result = {
        "tool": "website-clicks-improver",
        "settings": {
            "site": args.site, "brand_terms": brand_terms, "min_impr": args.min_impr,
            "min_impr_p23": args.min_impr_p23, "min_pair_impr": args.min_pair_impr,
            "ctr_threshold": args.ctr_threshold, "benchmark": args.benchmark,
            "ctr_curve": {str(k): round(v, 4) for k, v in sorted(curve.items())},
            "expected_ctr_pos5": round(ctr5, 4),
        },
        "data_mode": data_mode,
        "date_range": args.date_range or "; ".join(sorted(store["date_ranges"])) or None,
        "log": store["log"],
        "warnings": store["warnings"],
        "summary": {
            "pages_in_data": int(len(pages)),
            "page_query_rows": int(len(pairs)),
            "total_clicks": int(tot_clicks), "total_impressions": int(tot_impr),
            "site_ctr": round(tot_clicks / tot_impr, 4) if tot_impr else 0,
            "low_ctr_pages": int(len(low)), "low_ctr_extra_clicks": int(low["extra_clicks"].sum()),
            "page23_pages": int(len(p23)), "page23_clicks_at_pos5": int(p23["clicks_at_pos5"].sum()),
            "cannibalised_queries": len(cannibal),
        },
        "low_ctr_pages": rows(low, ["ctr_ratio", "extra_clicks", "priority"]),
        "page23_pages": rows(p23, ["serp_page", "clicks_at_pos5", "priority"]),
        "pages_to_fetch": focus,
        "page_queries": page_queries,
        "cannibalisation": cannibal,
        # Compact site-wide page list, used for internal-link source suggestions.
        "all_pages": [{"page": r["page"], "clicks": int(r["clicks"]), "impressions": int(r["impressions"]),
                       "position": round(float(r["position"]), 1)}
                      for r in pages.sort_values("clicks", ascending=False).head(500).to_dict("records")],
        "pair_index": ({} if pairs.empty else {
            url: [q for q in g.sort_values("impressions", ascending=False)["query"].head(25)]
            for url, g in pairs[pairs["impressions"] >= args.min_pair_impr].groupby("page")
        }),
    }
    for r in result["low_ctr_pages"]:
        r["ctr_ratio"] = round(float(r["ctr_ratio"]), 2)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False))

    s = result["summary"]
    print(f"Data mode: {data_mode}  |  pages: {s['pages_in_data']}  |  page+query rows: {s['page_query_rows']}")
    print(f"Site: {s['total_clicks']:,} clicks / {s['total_impressions']:,} impressions / CTR {s['site_ctr']:.2%}")
    print(f"A) Low-CTR page-1 pages: {s['low_ctr_pages']}  (~{s['low_ctr_extra_clicks']:,} extra clicks at benchmark CTR)")
    print(f"B) Page 2-3 pages:       {s['page23_pages']}  (~{s['page23_clicks_at_pos5']:,} clicks if they reached position 5)")
    print(f"D) Cannibalised queries: {s['cannibalised_queries']}")
    print(f"Pages to fetch next:     {len(focus)}")
    for w in store["warnings"]:
        print("WARNING:", w)
    print(f"Saved -> {args.out}")


if __name__ == "__main__":
    main()
