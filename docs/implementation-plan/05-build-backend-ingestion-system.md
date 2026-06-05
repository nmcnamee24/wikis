# Step 05: Build The Backend Ingestion System

## Goal

Move from local scripts to a reliable backend pipeline that creates and updates Wikis topics from Wikipedia.

The backend should support both manual/batch ingestion and lazy on-demand ingestion, but live generation should not be required for the feed to feel fast.

## Build

Build ingestion as workers or admin-only API endpoints.

Pipeline:

```text
title submitted
  -> fetch Wikipedia source
  -> store source snapshot
  -> extract links
  -> extract images
  -> score image candidates
  -> run LLM condensation
  -> validate result
  -> store draft topic
  -> approve or reject
```

Runtime model:

```text
feed asks for next topic
  -> return approved cached topic if available
  -> return acceptable provisional topic if policy allows
  -> enqueue polished node generation in background
  -> enqueue edge generation for visible next hops
  -> keep wider candidates as metadata only
```

The ingestion system should treat topic cards and graph edges as separate generated chunks. Node generation creates readable content. Edge generation creates typed, ranked, validated navigation relationships.

## Tasks

1. Implement Wikipedia fetch service. Done via `scripts/wiki_to_card.py`.
2. Implement redirect/title normalization. Done.
3. Store page ID and revision ID. Done in source snapshots and card JSON.
4. Extract first-paragraph links. Done with lead-section fallback.
5. Extract image candidates and licenses. Done for Wikipedia page image metadata.
6. Implement image scoring rules. Done.
7. Implement LLM prompt and response schema. Done for OpenAI structured output, with local deterministic fallback.
8. Validate LLM output. Done.
9. Store draft card generations. Done via `scripts/backend_ingest.py`.
10. Add approve/reject workflow through scripts or a minimal internal page. Done via CLI review SQL.
11. Add retry and failure logging. Done via `ingestion_jobs` attempts/status/error fields.
12. Add batch ingestion for topic lists. Done via `--titles-file`.
13. Add candidate queue for missing related topics. Done via `candidate_edges` and queued edge jobs.
14. Add `skip if already cached` behavior. Done via `--skip-cached`.
15. Add background expansion from approved topics. Done via `enqueue-frontier`.
16. Add node generation statuses: `missing`, `provisional`, `generating`, `ready`, `failed`. Done in migration 005.
17. Add edge generation statuses: `missing`, `provisional`, `generating`, `ready`, `failed`. Done in migration 005.
18. Add generation version/hash fields for node and edge jobs. Done.
19. Add lock ownership so repeated jobs do not duplicate or corrupt chunks. Done via `generation_locks` and job lock fields.
20. Add hard frontier caps for background expansion. Done via `--frontier-limit` and `--max-jobs`.

## Current Implementation

Implemented:

- `scripts/backend_ingest.py`
- `migrations/003_ingestion_workflow.sql`
- `migrations/004_allow_culture_pillar.sql`
- `migrations/005_ingestion_generation_state.sql`
- `docs/step-05-backend-ingestion-usage.md`

The implementation is intentionally script/SQL based. It supports manual ingestion, batch ingestion, review-gated publication, retryable failure records, idempotent upserts, lock ownership, node/edge generation state, and capped frontier queueing. It does not require live generation on every swipe.

## Acceptance Criteria

- Backend can ingest one topic end-to-end.
- Backend can batch-ingest at least 100 topics.
- Failed ingestion is observable and retryable.
- LLM output is stored with provider/model/prompt version.
- Ready cards are not production-visible until approved.
- Provisional cards meet a minimum product-quality bar before display.
- Image attribution is preserved.
- Missing related topics can be queued without blocking the user.
- Already-generated topics are reused from cache.
- Node and edge generation jobs are idempotent.
- Background expansion cannot recursively fan out through popular hubs.

## Do Not Build Yet

- Fully featured CMS
- Public editor tools
- Automatic high-risk publication
- Live ingestion on every user swipe
- Full Wikipedia mapping
- Recursive frontier generation
