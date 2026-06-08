# Traversal Engine

## V1 Rule

V1 traversal is Supabase-only.

The app must not use bundled JSON, generated local card files, local graph smoke tests, or a client-side fallback graph. If Supabase cannot provide a topic or route, the app should show a bounded error instead of inventing a card or silently falling back.

## Runtime Path

```text
iOS FeedStore
  -> Railway API
  -> Supabase Postgres
  -> explicit topic_edges rows
  -> next topic response
```

`GET /v1/topics/{topic_id}` loads a topic from Supabase.

`POST /v1/feed/next` receives:

- current topic id
- gesture
- explored topic ids
- saved topic ids
- prototype-content flag

The API loads approved topics and approved edges from Supabase, scores eligible edges, and returns the selected topic. If no edge exists for the gesture, the endpoint fails. It does not return pending cards and does not queue background generation from feed traffic.

## Edge Source

Edges are explicit product data in `topic_edges`.

An edge should exist only when it has an intentional product reason:

- `deeper`: a more specific mechanism, component, or subtopic
- `prerequisite`: a concept that helps the current topic make sense
- `neighbor`: a nearby idea in the same area
- `contrast`: a comparison or counterpoint
- `person`: a relevant person
- `place`: a relevant place
- `teleport`: a deliberate jump to a different area

## Reset State

After a graph reset, `topic_edges` may be empty while topics remain available. In that state:

- the feed can load the startup topic from Supabase
- swiping will fail until explicit edges are rebuilt
- the map shows only the user's explored path
- no local data is used to mask missing graph data

## Scoring

The current backend scorer is a simple deterministic ranker over existing Supabase edges. It considers edge strength, confidence, topic quality, source confidence, novelty, visual strength, saved affinity, repetition, and sensitivity. This is acceptable for V1 only after the edge set itself is intentionally rebuilt.

## Non-Goals

V1 should not include:

- local seed graph loading
- checked-in generated card JSON
- checked-in generated graph JSON or HTML
- automatic Wikipedia-link edge creation
- feed-triggered graph generation
- client-side traversal fallback
