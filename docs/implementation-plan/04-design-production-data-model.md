# Step 04: Design The Production Data Model

## Goal

Create the production schema for topics, Wikipedia source snapshots, LLM generations, image candidates, graph edges, users, and exploration events.

## Build

Design the database before implementing ingestion workers.

Recommended base:

- Postgres
- Supabase or custom backend
- object storage/CDN for images if caching transformed assets

## Tasks

1. Define `topics`. Done in `migrations/001_production_schema.sql`.
2. Define `topic_source_snapshots`. Done.
3. Define `llm_card_generations`. Done.
4. Define `topic_edges`. Done.
5. Define `candidate_edges`. Done.
6. Define `image_candidates`. Done.
7. Define `topic_assets`. Done.
8. Define `users` or anonymous identities. Done as `app_users`.
9. Define `exploration_events`. Done.
10. Define `saved_topics`. Done.
11. Define review/status fields. Done across topics, generations, edges, candidates, and users.
12. Write migrations. Done.
13. Seed the Step 02 graph into the database. Done via generated seed SQL.

## Artifacts

- `migrations/001_production_schema.sql`
- `migrations/002_seed_step02_graph.sql`
- `scripts/seed_production_db.py`

## Apply

```sh
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/001_production_schema.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/002_seed_step02_graph.sql
```

Or regenerate and optionally apply the seed migration:

```sh
python3 scripts/seed_production_db.py
python3 scripts/seed_production_db.py --execute --database-url "$DATABASE_URL"
```

The seed SQL is deterministic and idempotent. Re-running the generator or SQL should update existing rows rather than duplicating topics, snapshots, generations, assets, approved edges, or candidate edges.

## Seed Coverage

The Step 02 seed graph currently maps into production tables as:

- 100 topics
- 100 Wikipedia source snapshots
- 100 card-generation records
- 715 approved topic edges
- up to 100 queued candidate topics expanded into candidate-edge rows
- selected Wikipedia image candidates where available
- one approved topic asset per topic, using either the selected image or a pillar background placeholder

## Current Caveat

The prototype card/image pipeline did not fetch full Wikimedia license records yet. Selected image rows preserve URL, source title, dimensions, quality score, and attribution text, while license is marked `unverified_wikimedia_license` until the Step 05 ingestion system fetches definitive media metadata.

## Acceptance Criteria

- Schema can represent source traceability.
- Every LLM card links to a source snapshot.
- Every selected image has attribution/license metadata.
- Candidate edges are separate from approved traversal edges.
- Exploration history can power map/profile.
- Account deletion is possible if accounts exist.

## Do Not Build Yet

- Admin UI beyond simple scripts
- Complex recommendation tables
- Multi-language support
- Payments
