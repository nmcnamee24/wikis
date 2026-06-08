# Step 12: Scale To A Large Audience

## Goal

Grow Wikis from a launched app into a large-scale curiosity engine with a huge topic graph and many users.

The joke version is "a bajillion users." The real version is an app that can handle mass usage without losing content quality or product focus.

## Build

Scale in this order:

1. content graph
2. infrastructure
3. personalization
4. distribution
5. community-assisted mapping
6. monetization, only if it fits the product

## Tasks

1. Expand from hundreds to tens of thousands of topics.
2. Automate topic ingestion with review queues.
3. Add stronger LLM grounding checks.
4. Add better image scoring and fallback backgrounds.
5. Improve traversal ranking from real usage data.
6. Add personalization without creating a retention trap.
7. Add caching/CDN for fast global load times.
8. Add backend autoscaling.
9. Add editorial tooling for high-risk topics.
10. Add multilingual support if demand exists.
11. Add collections or saved paths if users need organization.
12. Add lightweight search only when the graph is large enough to justify it.
13. Consider iPad/web only after iPhone core loop is strong.
14. Add community tools for reviewing transitions, reporting weak cards, and improving edge quality.
15. Track collective progress toward mapping useful Wikipedia, not all Wikipedia blindly.

## Community Mapping Later

Community can become a powerful long-term feature, but it should come after the core product works.

Good community contributions:

- flag inaccurate or boring cards
- suggest better curiosity hooks
- rate whether a transition made sense
- classify an edge as deeper, neighbor, prerequisite, person, place, or teleport
- rebuild and audit explicit graph edges
- build optional public rabbit holes

Avoid community mechanics that turn Wikis into social media:

- follower counts
- public status contests
- comment wars on every card
- leaderboards as the main motivation

## Growth Channels

Possible channels:

- App Store search
- short demo videos showing a rabbit hole
- education/curiosity creators
- science/history/literature communities
- "replace one doomscroll with one idea" positioning
- shareable static map snapshots post-V1

## Scale Metrics

Track:

- daily learning starts
- satisfying exits
- topic quality score
- traversal continuation quality
- bad-card report rate
- crash-free sessions
- API latency
- graph coverage
- image fallback rate
- source refresh age

## Risks At Scale

- LLM hallucination
- Wikipedia source drift
- weak images damaging polish
- controversial topics slipping through
- traversal feeling random
- over-optimizing for retention
- graph becoming too broad and shallow
- App Store reviews calling it "just Wikipedia"

## Guardrails

Keep:

- source traceability
- concise cards
- private learning profile
- gesture clarity
- four-pillar simplicity
- map as progression, not browsing

Do not let growth turn Wikis into:

- social media
- a generic AI answer app
- a noisy encyclopedia browser
- a gamified streak machine

## Long-Term Vision

At scale, Wikis becomes a personal map of human knowledge.

The app still opens to one idea.

The system behind it becomes massive:

```text
Wikipedia-scale source graph
+ LLM condensation
+ image intelligence
+ traversal ranking
+ personal exploration memory
+ private knowledge map
```
