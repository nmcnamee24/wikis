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
- created_at
- updated_at

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
- created_at
- updated_at

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
