# Wikipedia Map Inspiration

## Source

Reference repo:

```text
https://github.com/controversial/wikipedia-map.git
```

License:

MIT License, copyright Luke Deen Taylor.

## What It Does

The project visualizes connections between Wikipedia pages.

Its core interaction:

1. User enters or opens a Wikipedia topic.
2. The app creates a node for that topic.
3. User expands the node.
4. The app fetches the Wikipedia page.
5. It parses the lead section HTML.
6. It extracts Wikipedia article links from the first meaningful paragraph.
7. It adds those linked articles as child nodes in a graph.

This produces a compact map of closely related concepts without crawling an entire article.

## Why It Matters For Wikis

The strongest reusable idea is not the visible map. Wikis should not become a graph browser.

The valuable idea is using Wikipedia's first-paragraph links as relevance-biased related-topic edges.

First-paragraph links tend to be useful because:

- they are usually core concepts needed to understand the topic
- there are normally only a manageable number
- they are less noisy than all links in the article
- they expose natural rabbit-hole paths
- they can be retrieved from a public source

For example:

```text
Black Holes
  -> Event Horizon
  -> Gravity
  -> Spacetime
  -> General Relativity
```

Those are not automatically the final Wikis route, but they are the right raw material for the mapping engine.

## Useful Implementation Details

The project uses the Wikipedia API:

```text
https://en.wikipedia.org/w/api.php
```

Relevant calls:

- `action=parse`
- `prop=text`
- `section=0`
- `redirects=1`

The parser then:

- parses the returned HTML
- finds the first body paragraph that is not empty
- extracts `<a>` links where `href` starts with `/wiki/`
- filters out non-article namespaces by excluding titles with colons
- normalizes titles by replacing underscores with spaces
- removes duplicates
- follows redirects so nodes do not split accidentally

## What To Borrow

Borrow these ideas:

- first-paragraph link extraction
- redirect-aware title normalization
- duplicate-node prevention
- parent/path tracking
- graph serialization for saved exploration states
- visual traceback from a node to its origin
- random article as a possible teleport seed

## What Not To Borrow Directly

Do not directly borrow these product behaviors:

- user-entered search as the primary experience
- graph browsing as the main screen
- expanding many nodes manually
- opening Wikipedia pages as the core action
- treating all extracted links as equally good

Wikis is a curated swipe experience. Wikipedia Map is an exploratory graph tool.

## How Wikis Should Use This

Use Wikipedia Map's approach as an ingestion layer inside the larger Wikis source pipeline.

```text
Raw Wikipedia article
  -> lead paragraph links
  -> candidate edges
  -> Wikipedia image candidates
  -> LLM card condensation
  -> Wikidata identity matching
  -> pillar classification
  -> edge type classification
  -> content quality scoring
  -> traversal scoring
  -> curated user-facing card
```

## Candidate Edge Classification

After extraction, each link should be classified into Wikis edge types:

- deeper
- neighbor
- prerequisite
- contrast
- origin
- person
- place
- teleport seed

Examples:

```text
Black Holes -> Event Horizon = deeper
Black Holes -> Neutron Stars = neighbor
Black Holes -> General Relativity = prerequisite
The Silk Road -> Central Asia = place
Relativity -> Einstein = person
```

## Why This Is Better Than Random Wikipedia Links

Wikis should avoid becoming:

```text
current_topic -> random_linked_article
```

The engine should instead do:

```text
current_topic
  -> candidate links from Wikipedia lead section
  -> candidate entities from Wikidata
  -> editorial graph scoring
  -> user-specific traversal decision
```

This preserves the "curiosity engine" idea while using Wikipedia as a knowledge substrate.

## V1 Practical Plan

For the prototype:

1. Write a small ingestion script that accepts a Wikipedia title.
2. Fetch the lead section through the Wikipedia API.
3. Extract first-paragraph links.
4. Normalize titles and redirects.
5. Store candidate edges in JSON.
6. Manually classify the best edges for 50 to 100 starter topics.
7. Use those curated edges in the SwiftUI prototype.

For backend V1:

1. Store candidate edges in Postgres.
2. Add an admin review status.
3. Run automatic pillar classification.
4. Run automatic edge-type suggestions.
5. Require review before high-risk topics enter production.

## Open Questions

- Should Wikis ingest from Wikipedia live, or only through an offline pipeline?
- How much should Wikidata relationships outweigh first-paragraph links?
- Should teleport candidates come partly from random Wikipedia articles?
- How should disambiguation pages be handled?
- Should pages with weak lead sections be skipped or enriched from other sources?

## Recommendation

Use this repo as an engine reference, not a product reference.

The best version of Wikis is:

```text
Wikipedia API source fetch
+ LLM-powered condensation
+ Wikipedia image selection
+ Wikipedia/Wikidata-powered graph discovery
+ gesture-specific traversal scoring
+ private learning map
```

That combination keeps the app grounded in real knowledge while avoiding the feeling of a raw Wikipedia browser.
