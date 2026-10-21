#!/usr/bin/env python3
"""
fetch_pages.py - Step 2 of the website-clicks-improver skill.

Fetches each page listed in analysis.json -> pages_to_fetch and extracts what matters for
CTR and keyword coverage: <title>, meta description, canonical, robots, H1-H3 outline,
main body text, word count, JSON-LD schema types and FAQ presence.

If the sandbox cannot reach the site, gather the content another way (a web-fetch tool,
the user pasting it) and pass it with --content-json:

  {
    "https://example.com/page/": {
      "title": "...", "meta_description": "...",
      "h1": ["..."], "headings": [["h2", "..."], ["h3", "..."]],
      "body_text": "full visible text of the page ..."
    }
  }

Usage:
  python fetch_pages.py work/analysis.json -o work/pages.json [--content-json manual.json]
         [--delay 1.0] [--timeout 20] [--no-fetch]
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover
    raise SystemExit("Install dependencies first: pip install requests beautifulsoup4")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36 website-clicks-improver/1.0")
STRIP_TAGS = ["script", "style", "noscript", "svg", "iframe", "form", "nav", "header", "footer", "aside"]


def clean(t: str | None) -> str:
    return re.sub(r"\s+", " ", t or "").strip()


def schema_types(soup: BeautifulSoup) -> list[str]:
    types: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            t = node.get("@type")
            if isinstance(t, str):
                types.add(t)
            elif isinstance(t, list):
                types.update(str(x) for x in t)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            walk(json.loads(tag.string or ""))
        except Exception:  # noqa: BLE001
            continue
    return sorted(types)


def parse_html(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title = clean(soup.title.string if soup.title else "")
    md = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    robots = soup.find("meta", attrs={"name": re.compile("^robots$", re.I)})
    canon = soup.find("link", rel=lambda v: v and "canonical" in v)
    types = schema_types(soup)

    for t in soup(STRIP_TAGS):
        t.decompose()
    root = soup.find("main") or soup.find("article") or soup.body or soup
    headings = [[h.name, clean(h.get_text(" "))] for h in root.find_all(["h1", "h2", "h3"])
                if clean(h.get_text(" "))]
    h1 = [t for lvl, t in headings if lvl == "h1"]
    if not h1:  # some themes put the H1 outside <main>
        h1 = [clean(h.get_text(" ")) for h in soup.find_all("h1") if clean(h.get_text(" "))]
    body = clean(root.get_text(" "))
    faq_q = sum(1 for _, t in headings if t.endswith("?"))
    return {
        "url": url,
        "status": "fetched",
        "title": title,
        "meta_description": clean(md.get("content") if md else ""),
        "canonical": canon.get("href") if canon else "",
        "robots": robots.get("content") if robots else "",
        "h1": h1,
        "headings": headings,
        "body_text": body,
        "word_count": len(body.split()),
        "schema_types": types,
        "question_headings": faq_q,
        "has_faq_schema": "FAQPage" in types,
    }


def norm_headings(raw) -> list[list[str]]:
    """Accept [["h2","text"]], ["text"] (treated as h2), [{"level":"H2","text":"..."}]."""
    out = []
    for h in raw or []:
        if isinstance(h, str):
            out.append(["h2", clean(h)])
        elif isinstance(h, dict):
            lvl = str(h.get("level") or h.get("tag") or "h2").lower()
            lvl = lvl if lvl.startswith("h") else f"h{lvl}"
            out.append([lvl, clean(h.get("text") or h.get("heading") or "")])
        elif isinstance(h, (list, tuple)) and len(h) >= 2:
            lvl = str(h[0]).lower()
            out.append([lvl if lvl.startswith("h") else f"h{lvl}", clean(str(h[1]))])
    return [h for h in out if h[1]]


def from_manual(url: str, d: dict) -> dict:
    d = d or {}
    body = clean(d.get("body_text") or "")
    headings = norm_headings(d.get("headings"))
    h1 = d.get("h1") or [t for lvl, t in headings if lvl == "h1"]
    if isinstance(h1, str):
        h1 = [h1]
    return {
        "url": url, "status": "manual",
        "title": clean(d.get("title") or ""), "meta_description": clean(d.get("meta_description") or ""),
        "canonical": d.get("canonical", ""), "robots": d.get("robots", ""),
        "h1": h1, "headings": headings, "body_text": body, "word_count": len(body.split()),
        "schema_types": d.get("schema_types") or [],
        "question_headings": sum(1 for _, t in headings if str(t).endswith("?")),
        "has_faq_schema": "FAQPage" in (d.get("schema_types") or []),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("analysis", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("work/pages.json"))
    ap.add_argument("--content-json", type=Path, help="Manually gathered page content (see docstring)")
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--timeout", type=int, default=20)
    ap.add_argument("--no-fetch", action="store_true", help="Only use --content-json")
    args = ap.parse_args()

    analysis = json.loads(args.analysis.read_text())
    urls = analysis.get("pages_to_fetch", [])
    manual_raw = json.loads(args.content_json.read_text()) if args.content_json else {}
    # match URLs with or without a trailing slash
    key = lambda u: u.strip().rstrip("/").lower()  # noqa: E731
    manual_by_key = {key(u): v for u, v in manual_raw.items()}
    manual = {u: manual_by_key[key(u)] for u in urls if key(u) in manual_by_key}
    unused = [u for u in manual_raw if key(u) not in {key(x) for x in urls}]
    if unused:
        print(f"WARNING: {len(unused)} URL(s) in --content-json are not in pages_to_fetch and were ignored:")
        for u in unused[:10]:
            print("   ", u)
    existing = json.loads(args.out.read_text()) if args.out.exists() else {}

    out: dict[str, dict] = {}
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept-Language": "en"})
    failed = []
    for i, url in enumerate(urls, 1):
        if url in manual:
            out[url] = from_manual(url, manual[url])
            print(f"[{i}/{len(urls)}] manual   {url}")
            continue
        if existing.get(url, {}).get("status") in ("fetched", "manual"):
            out[url] = existing[url]
            print(f"[{i}/{len(urls)}] cached   {url}")
            continue
        if args.no_fetch:
            out[url] = {"url": url, "status": "not_fetched", "error": "no content provided"}
            failed.append(url)
            continue
        try:
            r = session.get(url, timeout=args.timeout, allow_redirects=True)
            if r.status_code >= 400:
                raise RuntimeError(f"HTTP {r.status_code}")
            page = parse_html(r.text, url)
            page["final_url"] = r.url
            page["http_status"] = r.status_code
            out[url] = page
            print(f"[{i}/{len(urls)}] fetched  {url}  ({page['word_count']} words)")
        except Exception as e:  # noqa: BLE001
            out[url] = {"url": url, "status": "not_fetched", "error": str(e)[:200]}
            failed.append(url)
            print(f"[{i}/{len(urls)}] FAILED   {url}  -> {e}")
        time.sleep(args.delay)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"Saved -> {args.out}  ({len(urls) - len(failed)}/{len(urls)} pages with content)")
    if failed:
        print("\nPages without content (gather them with a web-fetch tool or ask the user, then re-run "
              "with --content-json):")
        for u in failed:
            print("  -", u)


if __name__ == "__main__":
    main()
