# Content System

## Editorial Standard

Wikis content must feel written by an excellent explainer.

It should not feel like:

- Wikipedia pasted into a card
- an academic abstract
- generic AI output
- trivia fragments
- SEO content

## Topic Card Template

```text
PILLAR

Topic Title

Short explanation.
The explanation should create a mental model, not recite a definition.

Curiosity hook:
One sharp reason this topic is stranger, deeper, or more important than it first seemed.
```

## Explanation Rules

Every explanation should:

- explain the thing in plain English
- include one concrete detail or image
- avoid unneeded dates unless chronology matters
- avoid overclaiming
- avoid moralizing
- fit in a 20 to 30 second read
- prepare at least one useful next topic

## Reading Block Rules

For now, write one plain explanatory block. Do not add a separate labeled hook section; any curiosity cue should be part of the normal paragraph.

## Example: Black Holes

```text
SCIENCE

Black Holes

A black hole is not really a hole. It is what happens when so much matter gets squeezed into one place that space itself bends inward. Past a boundary called the event horizon, even light cannot escape, which means the object becomes invisible except for how it affects everything around it.
```

## Example: The Silk Road

```text
HISTORY

The Silk Road

The Silk Road was not one road. It was a shifting network of trade routes that connected East Asia, Central Asia, the Middle East, and Europe for centuries. Silk moved through it, but so did spices, religions, technologies, diseases, stories, and political power.

The twist:
Its greatest cargo may not have been goods at all, but ideas moving between civilizations that rarely met directly.
```

## Source Strategy

Use Wikipedia as the default raw material, not as copy.

Preferred source layers:

1. Wikipedia API for page extract, lead section, links, and media
2. Wikidata IDs for entity identity and relationships
3. Britannica, Stanford Encyclopedia, NASA, Smithsonian, LOC, or other reputable sources for high-risk or specialized topics
4. LLM condensation into the Wikis card format
5. Internal editorial or automated review for final card text

## Wikipedia-To-Card Pipeline

Wikis content should be generated through a repeatable pipeline:

```text
Wikipedia title
  -> fetch page metadata, extract, lead HTML, links, and images
  -> clean and normalize source text
  -> send source packet to LLM
  -> produce short explanation and hook
  -> verify length, tone, hook, and source grounding
  -> store approved card
```

The LLM should not invent the card from memory. It should condense the fetched Wikipedia source packet.

## Provisional Cards

Provisional cards are allowed when navigation needs to stay responsive before full LLM condensation is ready.

A provisional card is not a loading disguise. It may be simpler than a polished card, but it still has to be acceptable as the user-facing product experience.

Provisional cards should:

- come from deterministic Wikipedia summary and lead-link parsing
- use the same topic-card shape as ready content
- avoid unsupported hooks or clever phrasing
- clearly preserve source grounding
- expose enough edge candidates for the next visible hops
- be replaced only on the next visit or after explicit refresh

Reject provisional cards that feel like raw Wikipedia paste, empty scaffolding, or a temporary placeholder.

## LLM Condensation Contract

Input:

- Wikipedia title
- page extract or lead section
- first-paragraph links
- image/media candidates
- pillar classification
- optional Wikidata facts

Output:

```json
{
  "title": "Black Holes",
  "pillar": "science",
  "explanation": "A short, vivid explanation grounded in the source packet.",
  "hookType": "why_it_matters",
  "hook": "Optional internal navigation cue; not displayed as a separate labeled section.",
  "relatedCandidates": ["Event Horizon", "Spacetime", "General Relativity"],
  "readingSeconds": 24,
  "confidenceNotes": ["No unsupported claims detected."]
}
```

Rules:

- Condense, do not copy.
- Use only source-supported claims.
- Prefer mental models over lists.
- Keep the card under 30 seconds.
- End with a valid hook.
- Flag weak or controversial source material instead of smoothing over it.

## AI Assistance Rules

AI is central to the product, but it must be source-grounded.

The LLM can draft, simplify, and generate candidate hooks from Wikipedia source packets. Production content still needs validation.

For each generated card, store:

- source IDs
- generation prompt version
- model/version used
- fact-check status
- reviewer status
- reading time estimate
- content risk level

## Risk Levels

### Low Risk

Examples:

- Saturn
- Black holes
- The printing press
- Greek mythology

Requires source check and automated quality checks.

### Medium Risk

Examples:

- historical conflicts
- political movements
- religious topics
- psychology claims

Requires stronger sourcing and review.

### High Risk

Examples:

- current conflicts
- medical advice
- living people
- active political disputes
- contested ethnic or national claims

Avoid in V1 unless reviewed manually.

## Content Anti-Patterns

Reject cards that:

- begin with "In today's world"
- say "plays a crucial role" without explaining why
- use vague abstractions instead of concrete explanation
- contain unsupported superlatives
- list facts with no narrative
- end without a hook
- use an image that misrepresents the topic
