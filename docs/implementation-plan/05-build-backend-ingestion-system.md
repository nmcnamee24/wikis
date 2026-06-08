# Step 05: Build The Backend Ingestion System

## Goal

Create and update Supabase topics from Wikipedia.

## Current Boundary

Topic ingestion writes topic content only. It does not create navigation edges or graph-expansion jobs.

```text
title submitted
  -> fetch Wikipedia source
  -> extract images
  -> run condenser
  -> store source snapshot
  -> store generated topic
  -> approve or reject
```

## Current Implementation

Implemented:

- `scripts/wiki_to_card.py`
- `scripts/backend_ingest.py`
- `migrations/003_ingestion_workflow.sql`
- `migrations/004_allow_culture_pillar.sql`
- `migrations/005_ingestion_generation_state.sql`

## Acceptance Criteria

- Backend can ingest one topic end-to-end.
- Backend can batch-ingest explicit title lists.
- Failed ingestion is observable.
- LLM output is stored with provider/model/prompt version.
- Image attribution is preserved.
- Generated content lands in Supabase.
- No checked-in generated topic artifacts are required.

## Out Of Scope

- automatic edge creation
- candidate edge staging
- recursive graph expansion
- live generation on user swipe
- local graph files
