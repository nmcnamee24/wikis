# Step 06: Build The Traversal Engine

## Goal

Build the server-side logic that turns gestures into excellent next-topic choices.

The traversal engine should prefer approved cached topics. If it discovers a promising missing topic, it should enqueue ingestion for later rather than making the user wait.

## Build

Create a traversal API:

```http
POST /v1/feed/next
```

It receives current topic, gesture, and user/session context. It returns the next topic and prefetch candidates.

## Tasks

1. Implement edge lookup by current topic.
2. Implement gesture-specific candidate pools.
3. Score down gestures for depth and prerequisites.
4. Score right gestures for neighborhood relevance.
5. Score left gestures for novelty and pillar jump.
6. Add repetition penalties.
7. Add source-confidence and quality filters.
8. Add sensitivity filters.
9. Add fallback logic.
10. Return reason codes for debugging.
11. Add prefetch candidates.
12. Write tests for each gesture.
13. Enqueue unmapped candidate topics for background ingestion.
14. Track when a fallback was used because a better candidate was not cached yet.

## Acceptance Criteria

- Down feels like a rabbit hole.
- Right feels like adjacent exploration.
- Left feels surprising but not nonsensical.
- Engine never returns unapproved topics.
- Engine avoids recent repeats.
- Engine has graceful fallback when a topic has weak edges.
- Reason codes make decisions debuggable.
- Missing topics are queued for ingestion without blocking feed interaction.

## Do Not Build Yet

- Black-box ML recommender
- Engagement-maximizing ranking
- Social signals
- Ad targeting
- User-facing community mapping
