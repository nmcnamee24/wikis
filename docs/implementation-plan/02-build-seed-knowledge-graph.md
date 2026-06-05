# Step 02: Build The Seed Knowledge Graph

## Goal

Turn generated Wikipedia cards into a small but navigable knowledge graph.

The first graph should be good enough to support the three gestures:

- down: continue deeper
- right: explore nearby
- left: teleport

This is the precomputed foundation for the app. Do not try to map all of Wikipedia here.

## Build

Create a curated seed graph with 100 to 300 topics.

Store it as local JSON first. The goal is fast iteration, not database purity.

The long-term system can lazily map Wikipedia as users explore, but V1 needs a strong cached starter graph so the first session feels instant and intentional.

## Tasks

1. Select starter topics across Science, Literature, Society, and History.
2. Run the Step 01 pipeline for each topic.
3. Normalize duplicate topics and redirects.
4. Create candidate edges from Wikipedia lead links.
5. Classify edges into Wikis edge types.
6. Add manually curated edges where Wikipedia links are weak.
7. Add teleport pools across pillars.
8. Reject low-quality or high-risk topics.
9. Create starter-topic pool for first sessions.
10. Export graph JSON for the iOS prototype.

## Hybrid Mapping Model

Use this model after the seed graph exists:

```text
curated seed graph
  -> user explores cached topics instantly
  -> missing related topics enter an ingestion queue
  -> background workers generate cards and edges
  -> approved topics become part of the cache
  -> future users see them instantly
```

Live generation should not block the main swipe path unless there is a polished instant fallback.

## Edge Types

Use:

- deeper
- neighbor
- prerequisite
- contrast
- origin
- person
- place
- teleport

## Acceptance Criteria

- 100 to 300 valid topics exist.
- Every topic has at least one down/right/left candidate or explicit fallback.
- No high-risk unreviewed topics are included.
- Starter pool contains at least 25 strong topics.
- Graph can produce 10-card rabbit holes without dead-ending.
- Pillar distribution is reasonably balanced.

## Current Implementation

Implemented:

- `scripts/build_seed_graph.py`
- `scripts/validate_seed_graph.py`
- `data/graph/seed_graph.json`
- `docs/step-02-seed-graph-usage.md`

Current seed graph:

- 100 prototype-pass topics
- 715 typed edges
- 100 starter-pool topics
- 100 exported candidate-queue topics for future ingestion
- 0 validation issues

Current pillar distribution:

- Science: 37
- Literature: 19
- Society: 23
- History: 21

Current edge types:

- deeper
- neighbor
- teleport

The current graph satisfies the lower bound of the Step 02 production target and gives every topic a down, right, and left path without live generation.

`scripts/validate_seed_graph.py` verifies the acceptance criteria directly, including the 100-topic lower bound, starter-pool size, pillar balance, image/fallback availability, per-topic gesture coverage, and 10-card rabbit-hole paths.

## Next Expansion Target

Before the iOS prototype is polished, consider expanding from 100 toward 300 topics by ingesting the highest-priority entries from `candidateQueue`.

Priority should favor:

- topics seen from multiple source cards
- topics with strong first-paragraph placement
- low-risk evergreen topics
- visually strong Wikipedia pages
- topics that fill pillar imbalance
- topics that create better down/right paths

## Do Not Build Yet

- Machine learning recommender
- Public admin dashboard
- Huge graph crawl
- User-specific ranking
- Full Wikipedia crawl
- Community mapping tools
