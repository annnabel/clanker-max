# AI Field Guide

A one-page reference guide to artificial intelligence, organised into nine sections with concept maps, plain-English topic cards, optional "Go deeper" panels, and a source for every factual claim.

Open `index.html` in a browser, or visit the GitHub Pages site for this repository.

## Status

Built in stages.

- **Stage 1 (14 Nov 2026):** page framework (navigation, search, concept maps, reading paths, glossary, myths index) and Section 1, *How AI Works* (33 cards).
- Sections 2–9 list their planned cards and will be researched and written in later stages.

## Source standards

- Tier 1: peer-reviewed papers, arXiv papers from known labs, filings, government and standards bodies, established research institutions (e.g. Stanford AI Index, Epoch AI, OECD).
- Tier 2: reputable journalism.
- Tier 3: company announcements, labelled "company claim".

Claims are labelled as facts (cited), estimates (attributed), or debates (each position attributed). Fast-moving facts carry an "as of" date. Where sources conflict, both are shown.

## Structure

Everything is in a single self-contained `index.html`: content lives in the `SECTIONS` and `SRC` objects inside the script, and the cards, maps, search, glossary and myths index are all generated from them.
