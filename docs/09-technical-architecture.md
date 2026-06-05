# Technical Architecture

## Recommended Production Stack

Native iOS:

- Swift
- SwiftUI
- Swift Concurrency
- SwiftData or Core Data for local cache and exploration history
- URLSession with typed API clients
- XCTest and XCUITest

Backend:

- Postgres
- server API for topics, graph traversal, and event ingestion
- object storage/CDN for images and reusable backgrounds
- background content pipeline for source ingestion and editorial review
- Wikipedia/Wikidata ingestion workers for topics, images, and graph edges
- LLM condensation workers for source-grounded topic cards

Recommended backend options:

- Supabase for speed and Postgres-first development
- Custom API with Node, Go, Python, or Swift server if business logic becomes complex

## High-Level Architecture

```text
iOS App
  -> Topic API
  -> Traversal API
  -> Event API
  -> Image CDN

Backend
  -> Postgres
  -> Content Pipeline
  -> Wikipedia/Wikidata Ingestion
  -> LLM Condensation
  -> Image Scoring
  -> Source Store
  -> Asset Store
  -> Admin/Review Tool
```

## iOS App Modules

```text
WikisApp/
  App/
  Features/
    Feed/
    Map/
    Profile/
  Core/
    API/
    DesignSystem/
    Models/
    Persistence/
    Analytics/
    Images/
    Routing/
  Tests/
```

## Backend Domain Models

### Topic

Represents a knowledge node.

Fields:

- id
- slug
- title
- pillar
- short_explanation
- hook_type
- hook_text
- reading_seconds
- source_confidence
- quality_status
- risk_level
- image_strategy
- image_asset_id
- generation_status
- generation_version
- generation_hash
- created_at
- updated_at

Topic generation statuses:

- missing
- provisional
- generating
- ready
- failed

`quality_status` controls editorial visibility. `generation_status` controls pipeline state. A topic can be provisionally available for navigation before it is ready as polished content.

### Topic Source Snapshot

Represents the Wikipedia source material used to generate a card.

Fields:

- id
- topic_id
- wikipedia_title
- wikipedia_page_id
- wikipedia_revision_id
- raw_extract
- lead_html
- link_candidates_json
- image_candidates_json
- fetched_at
- source_hash

### LLM Card Generation

Represents one LLM condensation attempt.

Fields:

- id
- topic_id
- source_snapshot_id
- provider
- model
- prompt_version
- generated_title
- generated_explanation
- generated_hook_type
- generated_hook_text
- grounding_status
- quality_status
- reviewer_notes
- created_at

### Topic Edge

Represents a graph connection.

Fields:

- id
- from_topic_id
- to_topic_id
- edge_type
- strength
- reason
- rank
- confidence
- generation_status
- generation_version
- generation_hash
- created_at
- updated_at

Edge generation statuses:

- missing
- provisional
- generating
- ready
- failed

Edges should be treated as first-class generated assets, not incidental fields on a topic. This allows navigation ranking, edge validation, A/B testing, and versioning to improve independently from the page text.

### Candidate Edge

Represents an unreviewed graph connection discovered from Wikipedia, Wikidata, or another source.

Fields:

- id
- source
- source_page_id
- from_title
- to_title
- normalized_to_title
- raw_position
- extraction_method
- candidate_strength
- proposed_edge_type
- status
- rejection_reason
- created_at
- updated_at

### Exploration Event

Represents a user transition.

Fields:

- id
- user_id
- session_id
- from_topic_id
- to_topic_id
- gesture
- reason_code
- dwell_ms
- saved
- created_at

### Topic Asset

Represents topic-specific images or reusable pillar backgrounds.

Fields:

- id
- topic_id nullable
- pillar nullable
- asset_type
- url
- attribution
- license
- quality_score
- approved

### Image Candidate

Represents one candidate image from Wikipedia media.

Fields:

- id
- topic_id
- source
- url
- thumbnail_url
- width
- height
- license
- attribution
- media_type
- quality_score
- rejection_reason
- selected
- created_at

## Progressive Topic Graph Generation

Wikis should behave like procedural generation, but the durable product asset is a progressively generated, versioned topic graph.

The feed must separate navigation responsiveness from semantic polish:

- Ready nodes are served immediately.
- Missing nodes can receive a deterministic provisional version from Wikipedia summary and lead-link parsing.
- Full LLM condensation happens in the background.
- Visible next hops are generated before invisible expansion.
- Candidate/radius expansion stays narrow and non-recursive.

### Node Chunks

A node chunk represents the topic card content.

Example:

```text
Black hole
- summary/page text
- pillar
- status
- version
```

Node generation owns:

- source snapshot
- provisional explanation
- polished explanation
- hook text
- pillar classification
- image strategy
- quality and review state
- generation version/hash

### Edge Chunks

An edge chunk represents a navigable relationship between two topics.

Example:

```text
Black hole -> Event horizon
- edge_type: deeper
- rationale
- rank
- confidence
- version
```

Edge generation owns:

- edge type
- rationale
- rank
- confidence
- source evidence
- validation status
- generation version/hash

This distinction matters because bad edges make the world feel random even when page prose is good. Navigation quality should be improved by re-ranking, validating, or regenerating edges without rewriting the current topic card.

### Runtime Policy

On traversal:

```text
feed asks for next topic
  -> serve ready topic if available
  -> otherwise serve acceptable provisional topic if allowed
  -> enqueue polished node generation in background
  -> enqueue edge generation for visible next hops
  -> cap expansion to the immediate frontier
```

The current visible page should not mutate while someone is reading. Store refined node and edge results, but apply them on the next visit or after an explicit refresh.

### Idempotency And Locks

Generation idempotency is required from day one.

Each node and edge generation job should include:

- stable node or edge identity
- source snapshot hash
- prompt version
- model/provider version
- generation version
- generation hash
- status
- lock owner
- started_at
- finished_at
- failure reason

Repeated jobs must not duplicate chunks, corrupt ready content, or overwrite a newer reviewed version with older output.

### Frontier Cost Policy

Background expansion must have hard limits.

For a missing or newly visited topic, generate:

- the current node
- at most two visible neighbor node chunks
- edge chunks for the visible next hops
- metadata-only candidate records for the remaining plausible links

Do not recursively generate every related topic. Popular hubs such as "Physics," "United States," and "World War II" should not fan out into unbounded content jobs.

## API Endpoints

### Ingest Wikipedia Topic

```http
POST /v1/admin/ingest/wikipedia
```

Request:

```json
{
  "title": "Black hole"
}
```

Pipeline:

```text
fetch Wikipedia source
  -> extract related links
  -> extract image candidates
  -> classify pillar
  -> generate LLM card
  -> score quality
  -> store as draft or approved topic
```

### Get Initial Topic

```http
GET /v1/feed/initial
```

Returns a starter topic and prefetched candidates.

### Resolve Next Topic

```http
POST /v1/feed/next
```

Request:

```json
{
  "currentTopicId": "black_holes",
  "gesture": "down",
  "sessionId": "session_123"
}
```

Response:

```json
{
  "topic": {},
  "reasonCode": "best_deeper_edge",
  "prefetch": []
}
```

### Save Topic

```http
POST /v1/topics/{topicId}/save
```

### Get Map

```http
GET /v1/me/map
```

### Get Profile

```http
GET /v1/me/profile
```

## Offline And Cache Behavior

The app should cache:

- current topic
- next candidate topics
- recently explored topics
- image assets
- profile summary

If offline:

- continue with cached prefetched topics
- save exploration events locally
- sync when online

## Security

Rules:

- no secrets in the app bundle
- server validates traversal events
- private user history is protected
- account deletion is supported if accounts exist
- analytics is privacy-conscious and minimal

## Build Strategy

Start with a local JSON graph to prove the interaction.

Then add:

1. backend topic API
2. Wikipedia/Wikidata candidate-edge ingestion
3. traversal endpoint
4. event tracking
5. profile/map data
6. content admin workflow
