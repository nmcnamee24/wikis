# Wikis

Wikis is a curiosity engine for learning one fascinating thing in about 30 seconds.

It is not a search engine, course platform, social network, or retention machine. The product promise is simple:

> Open the app, learn one fascinating thing, swipe if curiosity hits, and leave knowing more than you did before.

## Core Idea

Wikis is a Wikipedia-powered knowledge graph disguised as a swipe feed.

The core loop is:

```text
Supabase topic
  -> Railway API
  -> swipeable curiosity card
  -> explicit Supabase edge
  -> next Supabase topic
```

Every topic belongs to one of four navigation anchors:

- Science
- Culture
- Society
- History

The feed can move between anchors freely, but the pillars give the experience a consistent mental model and visual identity.

## Version 1

V1 has three screens:

- Feed
- Map
- Profile

No search. No friends. No comments. No public follower metrics. No onboarding. No notification habit loops.

## Planning Docs

- [Product Brief](docs/01-product-brief.md)
- [Experience Principles](docs/02-experience-principles.md)
- [Information Architecture](docs/03-information-architecture.md)
- [Feed UX](docs/04-feed-ux.md)
- [Content System](docs/05-content-system.md)
- [Traversal Engine](docs/06-traversal-engine.md)
- [Visual System](docs/07-visual-system.md)
- [Map And Profile](docs/08-map-and-profile.md)
- [Technical Architecture](docs/09-technical-architecture.md)
- [Analytics And Quality](docs/10-analytics-and-quality.md)
- [Roadmap](docs/11-roadmap.md)
- [Launch Checklist](docs/12-launch-checklist.md)

## Implementation Plan

Build Wikis in order. Each step has its own execution doc:

- [Step 01: Prove The Wikipedia-To-Card Pipeline](docs/implementation-plan/01-prove-wikipedia-to-card-pipeline.md)
- [Step 04: Design The Production Data Model](docs/implementation-plan/04-design-production-data-model.md)
- [Step 05: Build The Backend Ingestion System](docs/implementation-plan/05-build-backend-ingestion-system.md)
- [Step 06: Build The Traversal Engine](docs/implementation-plan/06-build-traversal-engine.md)
- [Step 07: Build The Native iOS App](docs/implementation-plan/07-build-native-ios-app.md)
- [Step 08: Build Map, Profile, And Local Memory](docs/implementation-plan/08-build-map-profile-local-memory.md)
- [Step 09: Add Quality, Safety, And Analytics](docs/implementation-plan/09-add-quality-safety-analytics.md)
- [Step 10: Run TestFlight Beta](docs/implementation-plan/10-run-testflight-beta.md)
- [Step 11: Launch On The App Store](docs/implementation-plan/11-launch-on-app-store.md)
- [Step 12: Scale To A Large Audience](docs/implementation-plan/12-scale-to-large-audience.md)

## Usage Docs

- [Step 01 Pipeline Usage](docs/step-01-pipeline-usage.md)
- [Step 05 Backend Ingestion Usage](docs/step-05-backend-ingestion-usage.md)
