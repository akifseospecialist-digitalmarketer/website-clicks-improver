#!/usr/bin/env python3
"""
find_gaps.py - Step 3 of the website-clicks-improver skill.

For every focus page it compares the queries the page already ranks for (from GSC) with
what the page actually says (from fetch_pages.py) and reports:

  * keyword gaps   - ranking queries the content does not use, or uses only partly
  * clusters       - gap queries grouped so ONE content chunk can cover several of them,
                     each with an intent, a suggested chunk type and a placement
  * snippet checks - title/meta problems that explain a low CTR
  * link sources   - stronger pages on the same site that should link to this page

Status per query:
  Used              phrase is in the body/headings and in the title, H1 or a heading -> no gap
  Not in headings   phrase is only in body copy (flagged for the page's top queries)
  Scattered terms   every word appears, but never as the phrase people search
  Partial           some words are missing from the page (listed in missing_terms)
  Missing           most words are missing

Usage:
  python find_gaps.py work/analysis.json work/pages.json -o work/gaps.json
         [--min-impr 10] [--max-per-page 20]
"""
from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path

STOP = set("""
a an the and or of for to in on at by with from as is are was were be been being am do does did
can could should would will shall may might must it its this that these those i me my we our you
your he she they them their what which who whom whose when where why how near vs versus than
into about over under up down out off so if then there here very just also not no yes s t
""".split())
QUESTION = {"how", "what", "why", "when", "where", "which", "who", "can", "does", "do", "is", "are",
            "should", "will", "much", "long"}
COST = {"cost", "costs", "price", "prices", "pricing", "cheap", "cheapest", "affordable", "fee", "fees",
        "rate", "rates", "payment", "finance", "financing", "afterpay", "quote", "budget", "billing", "bulk"}
COMPARE = {"vs", "versus", "compare", "comparison", "difference", "better", "alternative", "alternatives"}
LIST = {"best", "top", "review", "reviews", "types", "options", "ideas", "examples", "list"}
GENERIC = QUESTION | COST | COMPARE | LIST | {"long", "last", "time", "get", "best", "good", "need",
                                             "many", "online", "free", "service", "services"}
# Schema types that say nothing about a physical business. Anything else (Dentist, Plumber,
# Restaurant, LegalService, Store...) is treated as a LocalBusiness subtype.
NON_LOCAL_SCHEMA = {"WebPage", "WebSite", "Article", "BlogPosting", "NewsArticle", "BreadcrumbList", "ListItem",
                    "ItemList", "FAQPage", "Question", "Answer", "ImageObject", "VideoObject", "Person", "Organization",
                    "SearchAction", "EntryPoint", "ReadAction", "CollectionPage", "AboutPage", "ContactPage",
                    "Product", "Offer", "AggregateOffer", "AggregateRating", "Rating", "Review", "HowTo", "HowToStep",
                    "Thing", "CreativeWork", "SiteNavigationElement", "WPHeader", "WPFooter", "WPSideBar",
                    "PostalAddress", "GeoCoordinates", "OpeningHoursSpecification", "ContactPoint", "Brand",
                    "PropertyValue", "Service", "Event", "Recipe", "Course", "JobPosting", "SoftwareApplication"}
CTA_WORDS = {"book", "contact", "call", "appointment", "enquire", "enquiry", "quote", "touch", "visit"}


def tokens(text: str) -> list[str]:
    text = (text or "").lower().replace("’", "'").replace("'", "")
    return re.findall(r"[a-z0-9]+", text)


def stem(w: str) -> str:
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and re.search(r"(ch|sh|x|z|ss)es$", w):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    if len(w) > 5 and w.endswith("ing"):
        return w[:-3]
    if len(w) > 4 and w.endswith("ed"):
        return w[:-2]
    return w


def stems(text: str) -> list[str]:
    return [stem(t) for t in tokens(text)]


def key_stems(text: str) -> list[str]:
    return [stem(t) for t in tokens(text) if t not in STOP and len(t) > 1]


def phrase_count(q: str, text_stems_joined: str) -> int:
    """Count the query as a phrase, ignoring filler words: 'teeth whitening parramatta'
    matches 'teeth whitening in Parramatta'. Both sides use key_stems()."""
    qs = " ".join(key_stems(q))
    if not qs:
        return 0
    return len(re.findall(rf"(?:^| ){re.escape(qs)}(?= |$)", text_stems_joined))


def intent_of(q: str) -> str:
    t = tokens(q)
    ts = set(t)
    if ts & COMPARE or (" or " in f" {q.lower()} " and len(t) <= 8):
        return "Comparison"
    if ts & COST or "how much" in q.lower():
        return "Cost / pricing"
    if t and (t[0] in QUESTION or ts & {"how", "what", "why", "when", "where", "which", "who"}):
        return "Question"
    if "near me" in q.lower() or "nearby" in ts:
        return "Local (near me)"
    if ts & LIST:
        return "List / best"
    return "Topic / modifier"


CHUNK_FOR = {
    "Comparison": "Comparison table + 2-3 sentence verdict",
    "Cost / pricing": "Pricing section: price range or 'from $X', what changes the cost, payment options",
    "Question": "FAQ: the question as an H3 + a 40-60 word direct answer",
    "Local (near me)": "Local signals: suburb/area names, address, map, LocalBusiness schema (never add 'near me' literally)",
    "List / best": "List section: H2 + short bulleted options with one line each",
    "Topic / modifier": "New H2/H3 section (80-150 words)",
}


def placement_for(c: dict, heads: list, topic: set, page: dict, sitewide: set) -> str:
    """Where on the page the chunk should go, in words an editor can act on."""
    cstems = set(s for q in c["queries"] for s in key_stems(q))
    modifier = cstems - topic
    best, best_score = None, 0
    for lvl, t in heads:
        hs = set(key_stems(t))
        sc = len(modifier & hs) * 2 + len(cstems & hs)
        if sc > best_score:
            best, best_score = (lvl, t), sc
    cta = next((t for lvl, t in heads if set(tokens(t)) & CTA_WORDS), None)
    before_cta = f"before '{cta}'" if cta else "before the final call to action"
    first_h2 = next((t for lvl, t in heads if lvl == "h2"), None)
    qheads = [t for _, t in heads if t.endswith("?")]
    has_faq_block = page.get("has_faq_schema") or len(qheads) >= 3 or any(
        "faq" in t.lower() or "question" in t.lower() for _, t in heads)
    chunk, intent = c["chunk_type"], c["intent"]

    location_like = sitewide - GENERIC
    if intent == "Local (near me)" or (intent == "Topic / modifier" and modifier and modifier <= location_like):
        return "Intro paragraph (first 100 words), plus the H1 or title if it is a top query"
    if chunk.startswith("Heading edit"):
        return f"Rewrite {best[0].upper()} '{best[1]}'" if best else (
            f"Rewrite H2 '{first_h2}'" if first_h2 else "Add a new H2 using the phrase")
    if chunk.startswith("Sentence edit"):
        return f"An existing paragraph under '{best[1]}'" if best else "The intro paragraph"
    if intent == "Cost / pricing":
        price_head = next((t for _, t in heads if set(tokens(t)) & (COST | {"investment"})), None)
        if price_head:
            return f"Expand the section under '{price_head}'"
        if "cost" in topic or "price" in topic:
            return "Right after the intro - searchers on this page want the price first"
        return f"New 'Cost' section {before_cta}"
    if intent == "Comparison":
        return "Right after the intro (comparison table first)" if c["total_impressions"] and \
            {"vs", "versus"} & set(tokens(" ".join(c["queries"]))) and len(c["queries"]) > 2 else \
            f"New comparison section {before_cta}"
    if intent == "Question":
        if has_faq_block:
            return "Add to the existing FAQ / Q&A block"
        return f"New FAQ section {before_cta}"
    if best and best_score >= 3:
        return f"Under {best[0].upper()} '{best[1]}' (new H3 or extra paragraph)"
    return f"New H2 section {before_cta}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("analysis", type=Path)
    ap.add_argument("pages", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("work/gaps.json"))
    ap.add_argument("--min-impr", type=int, default=None,
                    help="Min impressions for a query to count (default: --min-pair-impr used in analyze_gsc.py)")
    ap.add_argument("--max-per-page", type=int, default=20)
    args = ap.parse_args()

    an = json.loads(args.analysis.read_text())
    pages = json.loads(args.pages.read_text())
    if args.min_impr is None:
        args.min_impr = an.get("settings", {}).get("min_pair_impr", 10)
    pq = an.get("page_queries", {})
    pair_index: dict[str, list[str]] = an.get("pair_index", {})
    clicks_by_page = {p["page"]: p["clicks"] for p in an.get("all_pages", [])}
    pos_by_page = {p["page"]: p["position"] for p in an.get("all_pages", [])}
    low_urls = {p["page"] for p in an.get("low_ctr_pages", [])}

    # Tokens common to most of the site's queries (city, brand, core service word) are useless
    # for matching link sources, so ignore them there.
    df_count = Counter()
    for qs in pair_index.values():
        df_count.update(set(s for q in qs for s in key_stems(q)))
    n_pages = max(1, len(pair_index))
    sitewide = {s for s, c in df_count.items() if c / n_pages > 0.4}

    out = {}
    for url in an.get("pages_to_fetch", []):
        page = pages.get(url, {})
        queries = [q for q in pq.get(url, []) if not q.get("is_brand") and q["impressions"] >= args.min_impr]
        entry = {"url": url, "content_status": page.get("status", "not_fetched"), "snippet_checks": [],
                 "gaps": [], "clusters": [], "link_sources": [], "top_queries": queries[:10]}
        out[url] = entry
        if page.get("status") not in ("fetched", "manual"):
            entry["snippet_checks"].append("Page content not available - gaps not checked.")
            continue

        title, meta = page.get("title") or "", page.get("meta_description") or ""
        h1s = page.get("h1") or []
        if isinstance(h1s, str):
            h1s = [h1s]
        heads = []
        for h in page.get("headings") or []:
            if isinstance(h, (list, tuple)) and len(h) >= 2 and str(h[0]).lower() in ("h2", "h3"):
                heads.append((str(h[0]).lower(), str(h[1])))
            elif isinstance(h, dict) and str(h.get("level", "")).lower() in ("h2", "h3", "2", "3"):
                heads.append(("h" + str(h["level"]).lower().lstrip("h"), str(h.get("text", ""))))
            elif isinstance(h, str):
                heads.append(("h2", h))
        body = page.get("body_text") or ""
        J = lambda s: " ".join(key_stems(s))  # noqa: E731
        title_j, meta_j, h1_j = J(title), J(meta), J(" | ".join(h1s))
        heads_j, body_j = J(" | ".join(t for _, t in heads)), J(body)
        page_keys = set(key_stems(" ".join([title, " ".join(h1s), " ".join(t for _, t in heads), body])))

        # Topic tokens = the page's core subject (H1 + words in at least half its queries)
        qcount = Counter(s for q in queries for s in set(key_stems(q["query"])))
        topic = set(key_stems(" ".join(h1s))) | {s for s, c in qcount.items() if queries and c / len(queries) >= 0.5}

        # ---------- snippet checks ----------
        checks = entry["snippet_checks"]
        tl, ml = len(title), len(meta)
        if tl == 0:
            checks.append("No title tag captured - add one (50-60 chars, top query first), or confirm the title manually.")
        elif tl > 60:
            checks.append(f"Title is {tl} chars - likely truncated in Google (aim for 50-60).")
        elif tl < 30:
            checks.append(f"Title is only {tl} chars - wasted space in the result; add the main keyword and a reason to click.")
        if not meta:
            checks.append("No meta description - Google writes its own snippet, often a weak one.")
        elif ml > 160:
            checks.append(f"Meta description is {ml} chars - likely truncated (aim for 140-155).")
        elif ml < 70:
            checks.append(f"Meta description is only {ml} chars - too thin to sell the click.")
        if queries:
            topq = queries[0]["query"]
            if not phrase_count(topq, title_j):
                checks.append(f"Top query '{topq}' is not in the title.")
            if meta and not phrase_count(topq, meta_j):
                checks.append(f"Meta description does not mention the top query '{topq}'.")
            top3 = set(s for q in queries[:3] for s in key_stems(q["query"]))
            if title and not (set(key_stems(title)) & top3):
                checks.append("Title does not match what people search for this page (generic title).")
            impr = sum(q["impressions"] for q in queries) or 1
            share = Counter()
            for q in queries:
                share[intent_of(q["query"])] += q["impressions"] / impr
            if share["Cost / pricing"] >= 0.2 and not (set(tokens(title + " " + meta)) & (COST | {"$"})):
                checks.append(f"{share['Cost / pricing']:.0%} of impressions are price searches but title/meta never mention price or cost.")
            if share["Question"] >= 0.2 and page.get("question_headings", 0) == 0:
                checks.append(f"{share['Question']:.0%} of impressions are questions but the page has no Q&A/FAQ headings.")
            if share["Comparison"] >= 0.2 and "table" not in body.lower():
                checks.append(f"{share['Comparison']:.0%} of impressions are comparison searches - a comparison table would match intent.")
            types = set(page.get("schema_types") or [])
            has_local = "LocalBusiness" in types or bool(types - NON_LOCAL_SCHEMA)
            if share["Local (near me)"] >= 0.15 and not has_local:
                checks.append("Strong 'near me' demand but no LocalBusiness-type schema found.")
        if title and h1s and title.strip().lower() == h1s[0].strip().lower() and tl < 35:
            checks.append("Title is just the H1 - write a separate, click-focused title tag.")
        if url in low_urls and not checks:
            checks.append("No obvious title/meta fault - check the live SERP: an AI Overview, featured snippet, "
                          "People Also Ask, local pack or ads may be taking the clicks. Also confirm Google "
                          "shows your title/meta and not a rewrite.")

        # ---------- query coverage ----------
        gaps = []
        for rank, q in enumerate(queries):
            text = q["query"]
            in_t, in_m, in_h1, in_h = (phrase_count(text, x) > 0 for x in (title_j, meta_j, h1_j, heads_j))
            n_body = phrase_count(text, body_j)
            ks = key_stems(text)
            present = [k for k in ks if k in page_keys]
            coverage = len(present) / len(ks) if ks else 1.0
            missing_terms = [w for w in tokens(text) if w not in STOP and stem(w) not in page_keys]
            in_struct = in_t or in_h1 or in_h
            if (n_body or in_h) and in_struct:
                continue  # Used
            if n_body and not in_struct:
                if rank >= 5:
                    continue
                status = "Not in headings"
            elif coverage >= 1.0:
                status = "Scattered terms"
            elif coverage >= 0.5:
                status = "Partial"
            else:
                status = "Missing"
            intent = intent_of(text)
            gaps.append({
                "query": text, "impressions": q["impressions"], "clicks": q["clicks"],
                "position": q["position"], "status": status, "intent": intent,
                "in_title": in_t, "in_meta": in_m, "in_h1": in_h1, "in_headings": in_h, "body_count": n_body,
                "coverage": round(coverage, 2), "missing_terms": missing_terms,
                "modifier": sorted(set(ks) - topic),
            })
        gaps.sort(key=lambda g: g["impressions"], reverse=True)
        gaps = gaps[: args.max_per_page]

        # ---------- clusters ----------
        # Price, comparison, question and local queries on one page are answered by ONE block
        # (a pricing section, a comparison table, an FAQ, a location paragraph). Topic/modifier
        # queries are grouped by the words they add on top of the page's core topic.
        MERGE_ALL = {"Cost / pricing", "Comparison", "Question", "Local (near me)"}
        clusters: list[dict] = []
        for g in gaps:
            mod = set(g["modifier"])
            target = None
            for c in clusters:
                if c["intent"] != g["intent"]:
                    continue
                if g["intent"] in MERGE_ALL:
                    target = c
                    break
                cm = set(c["_seed"])
                if (not mod and not cm) or (mod and cm and (
                        len(mod & cm) / len(mod | cm) >= 0.5 or mod <= cm or cm <= mod)):
                    target = c
                    break
            if target is None:
                target = {"id": f"C{len(clusters) + 1}", "label": g["query"], "intent": g["intent"],
                          "_seed": sorted(mod), "queries": [], "total_impressions": 0, "statuses": []}
                clusters.append(target)
            target["queries"].append(g["query"])
            target["total_impressions"] += g["impressions"]
            g["cluster"] = target["id"]
        for c in clusters:
            members = [g for g in gaps if g.get("cluster") == c["id"]]
            c["statuses"] = sorted({g["status"] for g in members})
            if c["intent"] == "Local (near me)":
                c["chunk_type"] = CHUNK_FOR["Local (near me)"]
            elif c["statuses"] == ["Not in headings"]:
                c["chunk_type"] = "Heading edit: work the phrase into an existing H2/H3 (and title/meta if it is the top query)"
            elif set(c["statuses"]) <= {"Scattered terms", "Not in headings"} and c["intent"] == "Topic / modifier":
                c["chunk_type"] = "Sentence edit: add the exact phrase naturally to an existing paragraph"
            else:
                c["chunk_type"] = CHUNK_FOR[c["intent"]]
            if c["intent"] == "Topic / modifier" and set(c["_seed"]) and set(c["_seed"]) <= (sitewide - GENERIC):
                c["chunk_type"] = "Location sentence: use the phrase once in the intro and once in a heading or the title"
            c["placement"] = placement_for(c, heads, topic, page, sitewide)
            del c["_seed"]
        clusters.sort(key=lambda c: c["total_impressions"], reverse=True)
        entry["gaps"], entry["clusters"] = gaps, clusters

        # ---------- internal link sources ----------
        # Core = the specific words of the page's top query. A source page qualifies when its
        # queries cover >= 60% of the core's IDF weight (rare words count more than common ones).
        if pair_index and queries:
            core = set(key_stems(queries[0]["query"])) - sitewide - GENERIC
            core = core or set(key_stems(queries[0]["query"]))
            weight = {k: math.log((n_pages + 1) / (df_count.get(k, 0) + 1)) + 0.1 for k in core}
            mass = sum(weight.values()) or 1
            p23q = [q for q in queries if 11 <= q["position"] < 31]
            on_page1 = pos_by_page.get(url, 99) < 11
            anchor = (queries[0] if on_page1 or not p23q else p23q[0])["query"]
            cands = []
            for other, oq in pair_index.items():
                if other == url:
                    continue
                okeys = set(s for q in oq for s in key_stems(q))
                overlap = core & okeys
                score = sum(weight[k] for k in overlap) / mass
                if score >= 0.6:
                    cands.append((round(score, 2), clicks_by_page.get(other, 0), other, sorted(overlap)))
            cands.sort(key=lambda c: (c[1], c[0]), reverse=True)
            for sc, clk, other, words in cands[:3]:
                entry["link_sources"].append({
                    "source": other, "source_clicks": clk, "anchor": anchor,
                    "why": f"Already ranks for '{' '.join(words)}' terms and earns {clk:,} clicks",
                })

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    n_g = sum(len(e["gaps"]) for e in out.values())
    n_c = sum(len(e["clusters"]) for e in out.values())
    print(f"Pages checked: {len(out)} | keyword gaps: {n_g} | content-chunk clusters: {n_c}")
    for url, e in out.items():
        print(f"\n{url}  [{e['content_status']}]")
        for c in e["snippet_checks"][:6]:
            print("   snippet:", c)
        for c in e["clusters"][:8]:
            print(f"   {c['id']} {c['intent']:<16} {c['total_impressions']:>6} impr  {c['queries']}  -> {c['placement']}")
    print(f"\nSaved -> {args.out}")


if __name__ == "__main__":
    main()
