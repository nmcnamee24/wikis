# Step 01: Prove The Wikipedia-To-Card Pipeline

## Goal

Prove that a Wikipedia topic can reliably become a Wikis card.

The pipeline may generate JSON only when an explicit output path is provided. V1 should not keep generated card artifacts in the repo.

## Current Implementation

Implemented:

- `scripts/wiki_to_card.py`
- `scripts/backend_ingest.py`

The production path is:

```text
Wikipedia title
  -> source fetch
  -> card generation
  -> SQL for Supabase
```

`scripts/backend_ingest.py ingest --execute` writes generated topic content to Supabase.

## Acceptance Criteria

- Topic content stores source page ID and revision ID.
- Card text is generated from source material.
- Image decision is explicit.
- Generated data lands in Supabase unless an explicit temporary output path is requested.
- No generated card directory is checked into the repo.
