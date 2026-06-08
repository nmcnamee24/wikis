# Step 04: Design The Production Data Model

## Goal

Create the production schema for Supabase topics, source snapshots, generated card text, images, explicit graph edges, users, and exploration events.

## Current Artifacts

- `migrations/001_production_schema.sql`
- `migrations/003_ingestion_workflow.sql`
- `migrations/004_allow_culture_pillar.sql`
- `migrations/005_ingestion_generation_state.sql`
- `migrations/006_enable_rls.sql`
- `scripts/apply_supabase_db.py`

## Current Boundary

The schema includes `topic_edges`, but no seed graph, generated edge data, or candidate-edge staging table is checked into the repo.

## Acceptance Criteria

- Schema can represent source traceability.
- Every generated card can link to a source snapshot.
- Every selected image can preserve attribution/license metadata.
- Explicit `topic_edges` can represent approved traversal routes.
- Exploration history can power map/profile.
- RLS is enabled on public app tables.
