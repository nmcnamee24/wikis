# Step 06: Build The Traversal Engine

## Goal

Build the server-side logic that turns gestures into excellent next-topic choices.

The traversal engine should prefer approved cached topics. If it discovers a promising missing topic, it should use only acceptable provisional content, enqueue generation for later, and keep the feed responsive.

## Build

Create a traversal API:

```http
POST /v1/feed/next
```

It receives current topic, gesture, and user/session context. It returns the next topic and prefetch candidates.

## Tasks

1. Implement edge lookup by current topic. Done in `GraphNavigator`.
2. Implement gesture-specific candidate pools. Done for down/right/left edge families.
3. Score down gestures for depth and prerequisites. Done.
4. Score right gestures for neighborhood relevance. Done.
5. Score left gestures for novelty and pillar jump. Done.
6. Add repetition penalties. Done using recent exploration history.
7. Add source-confidence and quality filters. Done.
8. Add sensitivity filters. Done with a small V1 penalty list.
9. Add fallback logic. Done.
10. Return reason codes for debugging. Done via `TraversalDecision.reasonCode`.
11. Add prefetch candidates. Done.
12. Write tests for each gesture. Done in `WikisCoreSmokeTests`.
13. Enqueue unmapped candidate topics for background ingestion. Done as capped `backgroundIngestionTopics`.
14. Track when a fallback was used because a better candidate was not cached yet. Done via `fallbackWasUsed`.
15. Generate visible next-hop edges before broader expansion. Represented by prefetch first, background candidates second.
16. Rank and validate edges independently from topic card text. Done through edge scoring and optional edge generation fields.
17. Prevent refined content from mutating the current visible page mid-read. Current engine returns an immutable decision snapshot.
18. Enforce frontier caps, such as two visible neighbors plus metadata-only candidates. Done via `TraversalContext.frontierLimit`.

## Current Implementation

Implemented:

- `Sources/WikisCore/GraphNavigator.swift`
- `Sources/WikisCore/WikisGraph.swift`
- `Sources/WikisCoreSmokeTests/main.swift`
- `App/Wikis/Sources/FeedStore.swift`
- `scripts/feed_next.py`
- `api/main.py`
- `railway.json`

The current engine is a deterministic rules scorer available in three forms:

- Swift core logic for the prototype.
- `scripts/feed_next.py` for local JSON and Supabase-backed backend dry runs.
- Hosted FastAPI endpoint at `POST /v1/feed/next` on Railway.

It returns the selected topic, full next-topic payload, reason code, selected edge, fallback candidates, prefetch candidates, capped background-ingestion candidates, fallback-used flag, and a debug summary. The API loads approved/prototype-pass topics from Supabase, avoids unapproved targets, applies repeat penalties, and exposes `/v1/events` so exploration history can be persisted.

Live endpoint:

```text
https://wikis-api-production.up.railway.app/v1/feed/next
```

## Acceptance Criteria

- Down feels like a rabbit hole.
- Right feels like adjacent exploration.
- Left feels surprising but not nonsensical.
- Engine never returns unapproved topics.
- Engine avoids recent repeats.
- Engine has graceful fallback when a topic has weak edges.
- Reason codes make decisions debuggable.
- Missing topics are queued for ingestion without blocking feed interaction.
- Provisional topics never feel like raw loading placeholders.
- Edge ranking can improve without rewriting topic card content.
- Popular hubs do not trigger unbounded background generation.

## Do Not Build Yet

- Black-box ML recommender
- Engagement-maximizing ranking
- Social signals
- Ad targeting
- User-facing community mapping
- Recursive candidate expansion
