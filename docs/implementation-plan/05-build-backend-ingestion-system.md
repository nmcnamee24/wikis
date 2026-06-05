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
  -> enqueue missing candidates in background
  -> never expose unapproved generated content directly
```

## Tasks

1. Implement Wikipedia fetch service.
2. Implement redirect/title normalization.
3. Store page ID and revision ID.
4. Extract first-paragraph links.
5. Extract image candidates and licenses.
6. Implement image scoring rules.
7. Implement LLM prompt and response schema.
8. Validate LLM output.
9. Store draft card generations.
10. Add approve/reject workflow through scripts or a minimal internal page.
11. Add retry and failure logging.
12. Add batch ingestion for topic lists.
13. Add candidate queue for missing related topics.
14. Add `skip if already cached` behavior.
15. Add background expansion from approved topics.

## Acceptance Criteria

- Backend can ingest one topic end-to-end.
- Backend can batch-ingest at least 100 topics.
- Failed ingestion is observable and retryable.
- LLM output is stored with provider/model/prompt version.
- Cards are not production-visible until approved.
- Image attribution is preserved.
- Missing related topics can be queued without blocking the user.
- Already-generated topics are reused from cache.

## Do Not Build Yet

- Fully featured CMS
- Public editor tools
- Automatic high-risk publication
- Live ingestion on every user swipe
- Full Wikipedia mapping
