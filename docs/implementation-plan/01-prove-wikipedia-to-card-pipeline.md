# Step 01: Prove The Wikipedia-To-Card Pipeline

## Goal

Prove that a Wikipedia topic can reliably become a Wikis card:

```text
Wikipedia title
  -> source fetch
  -> LLM condensation
  -> image selection
  -> related topics
  -> valid 30-second card
```

This is the core product risk. Do this before building a polished app.

## Build

Create a local script that accepts a Wikipedia title and outputs a complete topic JSON file.

Inputs:

- Wikipedia page title
- pillar override optional
- LLM provider/model

Outputs:

- normalized title
- Wikipedia page ID
- revision ID
- raw extract
- lead-section links
- image candidates
- selected image or fallback reason
- LLM explanation
- LLM hook
- related topic candidates
- quality checks

## Tasks

1. Call the Wikipedia API for page metadata and extract.
2. Fetch the lead section or first meaningful paragraph.
3. Extract main-namespace links from that paragraph.
4. Fetch image/media candidates from the page.
5. Rank image candidates by usefulness.
6. Send a source packet to the LLM.
7. Generate a Wikis-style explanation and hook.
8. Run local validation checks.
9. Save output as JSON.
10. Generate 20 sample cards across all four pillars.

## Acceptance Criteria

- At least 20 generated cards exist.
- Each card has a 20 to 35 second explanation.
- Each card ends with a valid hook.
- Each card has at least three related topic candidates.
- Each card records source page ID and revision ID.
- Image decision is explicit: selected Wikipedia image or pillar fallback.
- The output can be rendered in a simple mock without manual editing.

## Current Implementation

Implemented:

- `scripts/wiki_to_card.py`
- `scripts/validate_cards.py`
- `data/seed_topics.txt`
- `data/cards/*.json`
- `docs/step-01-pipeline-usage.md`

The script now:

- fetches Wikipedia page metadata, extract, page image, and lead HTML
- follows Wikipedia redirects through the API
- extracts first-paragraph article links
- falls back to broader lead-section links when the first paragraph is too sparse
- classifies a prototype pillar
- selects a Wikipedia image or records a pillar-background fallback
- generates either a deterministic prototype card or an OpenAI structured-output card
- validates explanation length, hook shape, related-topic coverage, and image choice
- writes one JSON file per topic

Current seed result:

- 100 generated topic cards
- 100 validation-pass cards
- 0 failing cards

The current pipeline supports both the local deterministic condenser and the source-grounded OpenAI condenser. The JSON contract is validated by `scripts/validate_cards.py` and by the consolidated Step 1-6 verifier.

## Do Not Build Yet

- Full iOS app
- User accounts
- Search
- Social features
- Production backend
- Complex personalization
