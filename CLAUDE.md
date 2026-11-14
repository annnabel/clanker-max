# AI Field Guide — project rules

## What this is
A single self-contained `index.html`: a reference guide to AI for a smart non-expert (uses AI tools, doesn't know how they work). Plain language in the main text; technical depth only in "Go deeper" panels. Published via GitHub Pages from `main`.

## Structure (MECE, do not change without asking)
9 sections, each answering one question:
1 How AI Works (built) · 2 Types of AI · 3 The AI Industry: Stack & Players · 4 History & Key Ideas · 5 Uses & Tools · 6 Economics & Markets · 7 Ethics, Risks & Society · 8 AI in Practice · 9 Looking Ahead.
Every topic lives in exactly one card. Placement rules: mechanism → 1, category → 2; concept → 1, milestone → 4; companies are tags, never cards; descriptive uses → 5, personal skills → 8; past → 4, future → 9; macro jobs → 7.3, individual job advice → 8.3; AI inside finance lives in 6.5 (5.2 only links to it). Include Australia specifically in regulation (7.6), geopolitics (7.7) and markets/ETFs (6.4).

## Code layout
All content is in the `SECTIONS` and `SRC` objects in the script. Planned cards are arrays `["id","Title"]`; built cards are objects with: id, title, level (Beginner|Intermediate|Deep), terms[], def, body[], example, links[[id,verb]], deeper[], optional myth[myth,fact], optional visual. Keep existing card ids (other cards and reading paths link to them). Set the section's `status:"built"` and `updated` date when done. Glossary, myths index, search and nav are generated automatically.

Inline markup in strings:
- `[[srcKey]]` footnote → must exist in SRC
- `{{est:Who|text}}` estimate · `{{op:Who|text}}` debate · `{{co:Company|text}}` company claim · `{{conf:|text}}` sources conflict · `{{asof:Mon YYYY}}` time-sensitive

Each built section gets a bespoke clickable SVG concept map (see `mapS1()`), replacing the preview grid:
2 = four-lens wheel with an "example system" picker · 3 = vertical layer cake with company chips + chokepoints + players toggle · 4 = timeline with era bands, winters shaded, hype line · 5 = industry × tool matrix · 6 = money-flow diagram · 7 = risks → responses + geopolitics cluster · 8 = skills ladder · 9 = branching futures.

## Source standards (strict)
- Tier 1: peer-reviewed papers, arXiv from known labs, company filings (10-K, earnings), government/regulator publications, standards bodies, Stanford AI Index, Epoch AI, OECD, IEA, METR.
- Tier 2: Reuters, FT, Bloomberg, The Economist, major newspapers, recognised experts.
- Tier 3: company blogs/announcements, always wrapped in `{{co:...}}`.
- Never: SEO farms, uncited listicles, hype sites, anonymous posts, vendor marketing as fact.

## Claim discipline
- Every factual claim, number or date has a `[[source]]` you actually opened this session. Never fill gaps from memory; leave the claim out or write UNVERIFIED.
- Label estimates/forecasts with who made them; date every fast-moving fact with `{{asof}}`.
- If sources conflict, show both with `{{conf:}}`.
- Contested topics (AGI timelines, bubble debate, existential risk, jobs): give the strongest version of each major position, attributed to who holds it.
- Watch for hype: vague superlatives, unattributed stats, projections stated as facts, numbers from a single vendor.
- Quotes under 15 words, max one per source; otherwise paraphrase.

## Readability (must hold)
- No text below 12px; body 17px. WCAG AA contrast in BOTH light and dark themes. All colours via CSS tokens.
- SVG text must use theme tokens (fill), never default black.
- Sources stay collapsed by default (per card "Sources (n)" and per section).
- Labels must not overlap in maps; check at desktop width and on a 390px phone (maps may scroll sideways).

## Before every commit
1. Open the page in a headless browser: zero console errors, zero broken internal links (`[data-go]` and `href="#..."` targets exist), every `[[key]]` exists in SRC.
2. Run a contrast check in light and dark.
3. Take one screenshot of each new map and fix overlaps.
4. Commit on a branch, open a PR, and summarise: cards added, sources used (by tier), claims left out as unverifiable, conflicts shown.
