# Technical Architecture

## Current V1 Shape

Wikis is Supabase-first.

```text
iOS app
  -> Railway FastAPI service
  -> Supabase Postgres
```

The app does not bundle graph JSON, generated topic JSON, or local traversal data.

## Runtime APIs

- `GET /v1/topics/{topic_id}` returns a Supabase topic.
- `POST /v1/feed/next` selects the next topic from explicit `topic_edges`.
- `POST /v1/events` records exploration events.
- `POST /v1/saved-topics` records saved topics.

## Data Boundaries

Topics and edges are separate product data.

`topics` stores readable cards. `topic_edges` stores navigation. Topic ingestion does not create edges.

The current reset state intentionally allows `topic_edges` to be empty. In that state, the app can load a topic but swiping fails with a bounded missing-route error.

## Edge Rebuild Boundary

The future Wikipedia-map edge builder should be a new, explicit pipeline. It should not be hidden inside topic-card ingestion, feed navigation, or local app resources.
