# Traversal Engine

## Product Role

The traversal engine is the real product.

The UI is a beautiful shell. The engine decides what the user sees next and whether the app feels magical or random.

In V1, the engine is powered primarily by Wikipedia:

- Wikipedia page links provide candidate related topics.
- First-paragraph links provide high-relevance candidates.
- Wikipedia images provide topic media when they are visually suitable.
- LLM-condensed summaries turn raw encyclopedia material into 30-second curiosity cards.

## Inputs

The engine receives:

- current topic
- current gesture
- user's explored topics
- user's saved topics
- recent swipe behavior
- pillar distribution
- graph edge types
- topic popularity
- novelty score
- difficulty score
- quality score
- source confidence
- image quality

## Wikipedia-Derived Graph

The external `controversial/wikipedia-map` project is useful because it demonstrates the core map behavior Wikis needs behind the scenes. Its key move is to expand a Wikipedia article by parsing the first body paragraph and extracting the linked article titles.

That is a good V1 candidate-source strategy because first-paragraph links are usually:

- few enough to rank
- more central than links buried later in the article
- grounded in actual Wikipedia editorial structure
- useful for creating a starting graph without hand-authoring every edge

For Wikis, these links are a primary source for related-topic traversal. They should still be typed, scored, filtered, and rewritten into the Wikis graph model before reaching the feed.

Recommended pipeline:

```text
Wikipedia page
  -> parse lead section / first meaningful paragraph
  -> extract main-namespace article links
  -> normalize titles and follow redirects
  -> create candidate edges
  -> fetch/score image candidates
  -> condense topic with LLM
  -> classify edge type
  -> score relevance, novelty, quality, and safety
  -> accept into Wikis traversal graph
```

## Outputs

The engine returns:

- next topic ID
- reason code
- fallback candidates
- prefetch candidates
- explanation of route for internal logs

Example:

```json
{
  "nextTopicId": "event_horizon",
  "reasonCode": "best_deeper_edge",
  "gesture": "down",
  "fallbackTopicIds": ["spacetime", "general_relativity"],
  "prefetchTopicIds": ["hawking_radiation", "neutron_stars", "the_silk_road"]
}
```

## Gesture Resolution

### Swipe Down

Goal:

Continue the rabbit hole.

Ranking preference:

1. Direct deeper edge from current topic
2. Prerequisite edge that unlocks a deeper idea
3. Strong causal or conceptual next step
4. Popular continuation with high quality

### Swipe Right

Goal:

Stay in the neighborhood.

Ranking preference:

1. Neighbor edge
2. Contrast edge
3. Same pillar, adjacent subtopic
4. Person/place connected to current topic

### Swipe Left

Goal:

Teleport.

Ranking preference:

1. Different pillar
2. High novelty
3. High standalone interest
4. Not recently shown
5. Strong image or pillar background
6. Not jarringly sensitive after a light topic

## Scoring Model

Initial V1 can use a weighted rules model before machine learning.

```text
score =
  edge_relevance * 0.30
  + user_interest_match * 0.20
  + novelty * 0.15
  + topic_quality * 0.15
  + source_confidence * 0.10
  + visual_strength * 0.05
  + popularity * 0.05
  - repetition_penalty
  - sensitivity_penalty
```

Weights should differ by gesture.

For teleport, novelty should be much higher. For continue, edge relevance should dominate.

## Cold Start

On first app open:

- choose from an editorially curated starter pool
- avoid sensitive or dry topics
- prioritize visual strength and broad fascination
- rotate across pillars

Starter pool examples:

- Black Holes
- Octopus Intelligence
- Pompeii
- The Silk Road
- The Fermi Paradox
- The Epic of Gilgamesh
- The Library of Alexandria
- Plate Tectonics

## Exploration Memory

The engine should avoid showing the same topic again too soon, but revisiting should be possible when it creates a meaningful loop.

Track:

- seen topic IDs
- saved topic IDs
- full path sequences
- longest path
- pillar balance
- repeated teleports
- abandoned topics
- read completion estimate

## Quality Gates

Never return a topic if:

- content quality is below threshold
- source confidence is below threshold
- image is broken and no fallback exists
- topic is high-risk and unreviewed
- topic has no valid outgoing candidates unless explicitly allowed

## V1 Implementation Strategy

Build in three phases:

1. Static graph with curated JSON
2. Wikipedia/Wikidata candidate-edge ingestion
3. Server-side traversal scorer
4. Personalization from exploration history

Do not start with a complex ML recommender. A good graph plus transparent scoring will be better for V1 and easier to debug.
