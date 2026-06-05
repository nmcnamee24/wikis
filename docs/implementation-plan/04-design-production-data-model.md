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
- `migrations/003_ingestion_workflow.sql`
- `migrations/004_allow_culture_pillar.sql`
- `migrations/005_ingestion_generation_state.sql`
- `migrations/006_enable_rls.sql`
- `scripts/seed_production_db.py`
- `scripts/apply_supabase_db.py`

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

The original seed cards preserve URL, source title, dimensions, quality score, attribution text, and an explicit license field. The Step 05 ingestion path now fetches Wikipedia image metadata and stores attribution/license metadata for newly ingested topics. If the app later caches transformed image assets in object storage, those transformed assets should keep the same source attribution fields.

## Live Verification

The schema and seed data are applied in Supabase. The consolidated verifier checks live counts for topics, source snapshots, LLM generation records, approved edges, candidate edges, ready topics, and the approved Ada Lovelace ingestion sample.

RLS is enabled on the public app tables. No direct anon/authenticated Data API policies are granted yet because the current app path uses the Railway API as the controlled server boundary.

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
