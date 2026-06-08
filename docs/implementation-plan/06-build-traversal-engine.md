# Step 06: Build The Traversal Engine

## Goal

Build the server-side logic that turns gestures into next-topic choices from Supabase.

## V1 Constraint

Traversal is API-only and Supabase-only.

Do not use:

- local seed graph JSON
- Swift client-side graph scoring
- generated local card data
- pending placeholder cards
- feed-triggered graph expansion
- automatic Wikipedia-link edges

## Current Implementation

Implemented:

- `scripts/feed_next.py`
- `api/main.py`
- `App/Wikis/Sources/FeedStore.swift`

`POST /v1/feed/next` loads topics and explicit `topic_edges` rows from Supabase, filters by gesture-compatible edge type, scores candidates, and returns the selected topic.

If no approved edge exists for a gesture, the endpoint fails. The iOS app surfaces that as a bounded route error.

## Acceptance Criteria

- App startup loads the first topic from Supabase.
- Feed navigation calls the Railway API.
- No local graph resource is bundled into the app.
- No client-side fallback route is used.
- Empty edge tables produce obvious missing-route behavior.
- Edge rebuilding is an explicit data task.
