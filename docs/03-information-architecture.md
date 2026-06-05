# Information Architecture

## App Structure

V1 contains three top-level screens:

- Feed
- Map
- Profile

The bottom tab bar contains only these three destinations.

## Pillars

Every topic belongs to exactly one primary pillar and may have secondary tags.

### Science

Includes:

- Physics
- Biology
- Astronomy
- Mathematics
- Technology
- Earth science
- Chemistry
- Medicine

### Literature

Includes:

- Books
- Mythology
- Language
- Poetry
- Storytelling
- Authors
- Folklore
- Rhetoric

### Society

Includes:

- Politics
- Economics
- Psychology
- Culture
- Sociology
- Law
- Religion
- Institutions

### History

Includes:

- Ancient civilizations
- Wars
- Empires
- Historical figures
- Archaeology
- Inventions
- Eras
- Migrations

## Pillars Are Anchors, Not Filters

The user should not feel locked into a category. The feed may jump from Science to History if the traversal engine decides that is the most curious move.

The pillar system exists to:

- establish visual language
- group progress in the profile
- help the graph remain legible
- prevent hundreds of exposed categories

## Topic Object

Each topic is a node in the knowledge graph.

Required fields:

```json
{
  "id": "black_holes",
  "title": "Black Holes",
  "pillar": "science",
  "summary": "Short editorial explanation.",
  "hookType": "the_weird_part",
  "hook": "Time behaves differently near the edge.",
  "imageStrategy": "topic_image",
  "imageAssetId": "black_hole_hero_01",
  "sourceIds": ["wikidata:Q589", "wikipedia:Black_hole"],
  "wikipediaPageId": 534366,
  "wikipediaTitle": "Black hole",
  "llmSummaryStatus": "approved",
  "relatedNodeIds": ["event_horizon", "neutron_stars", "hawking_radiation"],
  "deeperNodeIds": ["event_horizon", "spacetime", "general_relativity"],
  "teleportCandidateTags": ["ancient_history", "animal_intelligence", "language"],
  "readingSeconds": 25
}
```

## Source Object

Every topic should be traceable back to Wikipedia.

Required fields:

```json
{
  "topicId": "black_holes",
  "wikipediaTitle": "Black hole",
  "pageId": 534366,
  "revisionId": 1234567890,
  "extract": "Raw or cleaned source extract.",
  "leadHtml": "Optional lead section HTML.",
  "imageCandidates": [],
  "linkCandidates": [],
  "fetchedAt": "2026-06-05T00:00:00Z"
}
```

## Edge Types

The graph needs typed edges instead of generic links.

- `deeper`: moves down the rabbit hole
- `neighbor`: stays in the same topic area
- `teleport`: jumps to a high-novelty topic
- `prerequisite`: helps explain a harder topic
- `contrast`: reveals a useful opposite or comparison
- `origin`: moves to a historical or causal origin
- `person`: connects an idea to a figure
- `place`: connects an idea to a location

## Navigation Contract

The UI gestures map to graph behavior:

- Swipe down: choose the best `deeper` or `prerequisite` continuation
- Swipe right: choose the best `neighbor`, `contrast`, `person`, or `place`
- Swipe left: choose a high-novelty `teleport` topic
