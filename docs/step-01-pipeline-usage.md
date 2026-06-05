# Step 01 Pipeline Usage

## Purpose

This script proves the first Wikis production risk:

```text
Wikipedia topic
  -> Wikipedia API source fetch
  -> first-paragraph link mapping
  -> Wikipedia image decision
  -> condensed Wikis card JSON
```

## Run One Topic

```bash
python3 scripts/wiki_to_card.py "Black hole"
```

Output:

```text
data/cards/black-hole.json
```

## Run Seed Topics

```bash
python3 scripts/wiki_to_card.py --titles-file data/seed_topics.txt --delay 3 --skip-existing
```

## Current Condenser

The current condenser is deterministic and local. It exists so the full pipeline can run without API keys.

Production should replace it with a source-grounded LLM call that receives:

- Wikipedia title
- page ID and revision ID
- extract
- lead paragraph links
- image candidates
- pillar classification

The LLM must condense the fetched source packet, not answer from memory.

## JSON Shape

Each generated card includes:

- `source`: Wikipedia identity, revision, extract, and first paragraph
- `card`: title, pillar, explanation, hook, related candidates, reading seconds
- `mapping`: first-paragraph links and related candidates
- `image`: selected Wikipedia image or pillar fallback
- `quality`: prototype validation status and issues
