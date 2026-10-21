# CTR Playbook - diagnosing low CTR and rewriting titles + meta descriptions

Read this before writing suggestions for the **Low CTR Pages** tab.

## 1. Diagnose before you rewrite

Low CTR has a cause. Name it in the diagnosis, using the evidence in `gaps.json -> snippet_checks` and the
page's query list. Common causes, roughly in order of how often they're the culprit:

| Cause | Evidence | Fix |
|---|---|---|
| **Title doesn't match the searches** | Top queries not in the title; generic title ("Blog \| Brand", "Services") | Lead with the top query, phrased the way people search it |
| **Intent mismatch in the snippet** | 20%+ of impressions are price / question / comparison queries, but the title and meta never address them | Put the intent in the snippet: "Prices from $X", "How long it lasts", "X vs Y compared" |
| **Truncated title** | Title > 60 chars, so the important part is cut off | Front-load the keyword and the hook, drop filler and long brand strings |
| **Missing or thin meta** | No meta, or under 70 chars, so Google writes its own (often weak) | 140-155 char meta that answers the intent and ends with a reason to click |
| **No reason to click** | Title is just the keyword + brand | Add one hook: a number, a price, speed, proof, location, a guarantee, freshness |
| **Average position is misleading** | Page is #2 for a small query and #9 for the big one; the average says 5 | Judge CTR per query. Optimise the snippet for the query with the most impressions |
| **SERP features take the clicks** | No snippet faults, but CTR still low | Check the live SERP: AI Overview, featured snippet, People Also Ask, local pack, ads, video. Target the feature (40-60 word answer for snippets/AI Overviews; local signals for the pack) |
| **Google rewrites your title** | Live SERP shows a different title | Usually caused by long, stuffed or boilerplate titles, or a title that doesn't match the H1. Shorten, de-stuff, align title and H1 |
| **Wrong page ranking** | Cannibalisation tab shows two pages splitting the query | Choose one page to own the query; fix the other (see Page 2-3 playbook) |

Write the diagnosis in 1-2 plain sentences, e.g.:
> 43% of this page's impressions are price searches ("invisalign cost", "invisalign payment plans") but the
> title is just "Invisalign" (10 chars) and there's no meta description, so the result gives searchers no reason
> to pick it over clinics that show prices.

## 2. Title rules

- **50-60 characters** (Google shows ~580-600px). Hard maximum 60.
- **Lead with the top query** (most impressions), in the searchers' own wording. Put the location next to it for local services.
- **One hook** that matches the intent (see formulas below). Don't stack three.
- **Brand last**, and only if it fits. Use the short brand name.
- Title Case or sentence case, matching the site. No ALL CAPS, no emoji, no clickbait.
- A year only if the page really is updated for that year.
- Numbers, ranges and parentheses lift CTR when they're true: "(From $X)", "(2-3 Weeks)".
- Never promise what the page doesn't deliver. If the hook needs a fact you don't have, use `[placeholder]` and flag it.
- Always give 2 options: the recommended one, and an alternative with a different hook.

### Title formulas by intent

| Intent of the top queries | Formula | Example |
|---|---|---|
| Local service | `[Service] [Location] \| [Proof or offer]` | `Teeth Whitening Parramatta \| Results in One Visit` |
| Price | `[Topic] Cost [Location/Country]: [Price hook]` | `Invisalign Cost in Parramatta: Prices & Payment Plans` |
| Question / how-long / how-to | `[Question as searched]? [Short answer hint]` | `How Long Do Dental Implants Last? (Often 25+ Years)` |
| Comparison | `[A] vs [B]: [Criteria] Compared` | `Invisalign vs Braces: Cost, Speed & Comfort Compared` |
| List / best | `[N] Best [Thing] for [Audience] ([Qualifier])` | `7 Best Sedation Options for Nervous Patients` |
| Product / e-commerce | `[Product] - [Key attribute] \| [Price/shipping hook]` | `Oak Dining Table 6-Seater - Solid Wood \| Free Delivery` |
| Definition / what-is | `What Is [X]? [Benefit or plain-English hook]` | `What Is a Root Canal? Steps, Pain & Recovery Explained` |

## 3. Meta description rules

- **140-155 characters.** Never under 70, never over 160.
- Structure: **answer or offer -> proof or differentiator -> secondary keyword -> call to action.**
- Include the top query once and the second-biggest query if it reads naturally.
- Match the intent: price searches get a price signal, questions get the answer's first half, local searches get the suburb.
- End with an action: "Book online", "See prices", "Read the full guide", "Get a free quote".
- Google rewrites many metas anyway. A specific, intent-matched meta is the one most likely to be kept.

### Meta examples

| Weak | Better |
|---|---|
| `Harbour Dental offers teeth whitening.` (38) | `Professional teeth whitening in Parramatta: in-chair results in about an hour, plus take-home kits to keep your smile bright. Book online today.` (147) |
| *(none)* | `Invisalign in Parramatta from [price] with interest-free payment plans. Free 3D scan shows your results before you start. Book your consult.` (141) |

## 4. Other snippet fixes worth listing

- **H1** should agree with the title topic (Google rewrites titles that clash with the H1).
- **Schema**: `LocalBusiness` subtype for local services, `Product` + `Offer` for products, `Article` with dates for blogs,
  `BreadcrumbList` everywhere. FAQ rich results are now shown only for a small set of authoritative sites, so recommend FAQ
  content for the answers (and AI Overviews), not for guaranteed stars or dropdowns.
- **Review stars** can't come from a business marking up reviews of itself (self-serving reviews). Don't promise stars on
  service pages.
- **Freshness**: if the content is genuinely updated, show the updated date on the page.
- **URL**: don't change URLs just for CTR. The redirect risk usually outweighs the gain.

## 5. Self-check before saving

- [ ] Diagnosis cites real evidence (numbers, queries, snippet checks)
- [ ] Both titles <= 60 chars and lead with the top query
- [ ] Both metas 140-155 chars, contain the top query, end with a CTA
- [ ] Every hook is true or marked `[placeholder]`
- [ ] No two pages get the same title
