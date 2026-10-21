# Content Chunk Guide - writing the text to add for keywords a page ranks for but doesn't use

Read this before writing anything for the **Content Chunks** tab.

Each cluster in `gaps.json` gets **one chunk**: a piece of text an editor can paste onto the page where the
placement says. A chunk covers every keyword in its cluster, naturally.

## The rules

1. **Reader first.** The chunk must be useful to someone who typed that query. If it only exists to hold a
   keyword, don't write it.
2. **Answer first.** Open with the direct answer or the key fact in one sentence. AI Overviews, featured snippets
   and LLM answers lift self-contained passages that answer cleanly.
3. **Each keyword once, naturally.** Fix grammar ("teeth whitening parramatta" becomes "teeth whitening in Parramatta").
   Don't repeat the exact phrase, use variations. Never write keyword lists.
4. **Never "near me".** Use real place names, the address and the service area instead.
5. **No invented facts.** Prices, durations, stats, years, guarantees, awards: use what's on the page or what the
   user gave you. Otherwise write `[price range]`, `[years]` and list every placeholder in `notes`.
6. **Match the page's voice and language variant** (read pages.json -> body_text). Same person (we/you), same tone,
   same spelling (Australian/British/US).
7. **Respect page ownership.** If another page on the site owns the query (a dedicated cost page, a cannibalised
   query), write a 1-2 sentence teaser that links to that page instead of a competing section. Say so in `notes`.
8. **Link out where it helps.** Point to the related page on the site with a descriptive anchor.
9. **Keep it tight.** Use the lengths below. A chunk is a section, not an article.

## Templates by chunk type

The `content` field is plain text: `\n` for line breaks, `- ` for bullets, `Q:` / `A:` for FAQ pairs,
`| a | b |` lines for tables. `heading` holds the H2/H3 (blank for sentence or heading edits).

### Sentence edit (Scattered terms / Partial with 1 missing word)
Rewrite one existing sentence so the exact phrase appears. Give the **before -> after**.
```
Before: "Our team provides professional teeth whitening for adults..."
After:  "Our team provides professional teeth whitening in Parramatta for adults..."
```

### Heading edit (Not in headings)
Give the current heading and the new one. Keep it human.
```
H2 "Our Whitening Treatments" -> "Professional Teeth Whitening Treatments"
```

### Location sentence
One sentence for the intro (and a heading or title if it's a top query) that names the service and the real place.
```
"Looking for teeth whitening in Parramatta? Our clinic on [street] is a short walk from Parramatta Station."
```

### New H2/H3 section (80-150 words)
Heading uses the keyword naturally. First sentence answers. Then 2-4 sentences of specifics: how it works, who
it's for, what to expect. Close with a link or next step.

### FAQ (one Q&A per question in the cluster)
Use the question as searched, cleaned up, as an H3. Answer in **40-60 words**, with the direct answer in the first sentence.
```
Q: How long does teeth whitening last?
A: Professional teeth whitening usually lasts between [6 months and 2 years]. How long yours lasts depends on
   what you eat and drink, whether you smoke, and how well you look after your teeth. Touch-up trays from a
   take-home kit help keep results bright for longer.
```

### Pricing section
Price range or "from" price, what changes the price (3-5 factors), payment options, and a CTA. Placeholders
for any number not given.
```
heading: How much does Invisalign cost in Parramatta?
content: Invisalign treatment at our Parramatta clinic typically costs [price range], depending on how complex
your case is. Your exact price is confirmed after a 3D scan.
What affects the price:
- How much your teeth need to move
- Number of aligners required
- Whether you need refinements or retainers
Interest-free payment plans from [$X per week] are available. Book a consult for a personalised quote.
```

### Comparison table + verdict
4-6 rows of criteria the queries mention (cost, speed, comfort, look, maintenance), then a 2-3 sentence verdict
saying who should choose which.
```
| | Invisalign | Braces |
| Cost | [range] | [range] |
| Treatment time | Typically [x-y] months | Typically [x-y] months |
| Visibility | Nearly invisible | Visible brackets |
| Eating | Remove to eat | Avoid hard and sticky foods |
Verdict: ...
```

### List section
H2 plus 3-7 bullets, one line each, each bullet useful on its own.

### Local signals
Not a block of text. List concrete changes: suburb names in the intro, address and map, service-area sentence,
`LocalBusiness` schema with address and `areaServed`, consistent NAP, a link to the Google Business Profile.

## Placement

Use the placement from `gaps.json` unless you have a better one. Make it specific: name the heading the chunk goes
under or before. Price and comparison content for searchers who want it first goes right after the intro.
FAQs go in one FAQ block near the end, before the final call to action.

## Self-check before saving

- [ ] Every cluster has a chunk (or a note explaining why it was skipped or merged)
- [ ] Each keyword in the cluster appears once, naturally, with correct grammar
- [ ] Answers open with the answer; FAQ answers are 40-60 words
- [ ] Every unknown fact is a `[placeholder]` listed in `notes`
- [ ] No chunk competes with another page that owns the query
- [ ] Voice and spelling match the page
