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

## Source Strategy

Use Wikipedia as the default raw material, not as copy.

```text
Wikipedia title
  -> fetch page metadata, extract, and images
  -> clean and normalize source text
  -> condense into Wikis card text
  -> verify length, tone, and source grounding
  -> store topic content in Supabase
```

Topic-card generation does not create navigation edges.

## LLM Condensation Contract

Input:

- Wikipedia title
- page extract or lead section
- image/media candidates
- pillar classification

Output:

```json
{
  "title": "Black Holes",
  "pillar": "science",
  "explanation": "A short, vivid explanation grounded in the source packet.",
  "hookType": "why_it_matters",
  "hook": "A source-grounded curiosity cue.",
  "readingSeconds": 24,
  "confidenceNotes": ["No unsupported claims detected."]
}
```

Rules:

- Condense, do not copy.
- Use only source-supported claims.
- Prefer mental models over lists.
- Keep the card under 30 seconds.
- Flag weak or controversial source material instead of smoothing over it.

## Risk Levels

Low-risk examples:

- Saturn
- Black holes
- The printing press
- Greek mythology

Medium-risk examples:

- historical conflicts
- political movements
- religious topics
- psychology claims

High-risk examples:

- current conflicts
- medical advice
- living people
- active political disputes
- contested ethnic or national claims

Avoid high-risk topics in V1 unless reviewed manually.

## Content Anti-Patterns

Reject cards that:

- begin with "In today's world"
- say "plays a crucial role" without explaining why
- use vague abstractions instead of concrete explanation
- contain unsupported superlatives
- list facts with no narrative
- end without a hook
- use an image that misrepresents the topic
