# Step 05 Backend Ingestion Usage

Step 05 turns the local Wikipedia-to-card pipeline into a database-backed ingestion workflow.

Apply the workflow migrations after the Step 04 schema and Step 02 seed data:

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/003_ingestion_workflow.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/004_allow_culture_pillar.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/005_ingestion_generation_state.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/006_enable_rls.sql
```

Or apply the full schema/seed sequence with the repo helper:

```bash
python3 scripts/apply_supabase_db.py
```

The helper reads `DATABASE_URL` from `.env` by default, regenerates `migrations/002_seed_step02_graph.sql`, applies migrations `001` through `006`, and verifies the topic count. The Supabase dashboard connection string must contain the real URL-encoded database password, not the `[YOUR-PASSWORD]` placeholder.

## OpenAI Setup

Do not commit API keys. Keep a local key in your shell or an ignored `.env` file:

```bash
export OPENAI_API_KEY="replace-with-a-fresh-local-key"
export WIKIS_OPENAI_MODEL="gpt-5-mini"
```

The OpenAI condenser uses the Responses API with structured JSON output. If `OPENAI_API_KEY` is missing, use the default local condenser instead.

## Ingest One Topic

Generate SQL and local card JSON without touching the database:

```bash
python3 scripts/backend_ingest.py ingest "Ada Lovelace" \
  --cards-out data/cards \
  --sql-out /tmp/wikis_ingest_ada_lovelace.sql
```

Use the OpenAI content prompt:

```bash
python3 scripts/backend_ingest.py ingest "Ada Lovelace" \
  --condenser openai \
  --cards-out data/cards \
  --sql-out /tmp/wikis_ingest_ada_lovelace.sql
```

Apply directly to Postgres:

```bash
python3 scripts/backend_ingest.py ingest "Ada Lovelace" --condenser openai --execute
```

The script writes a draft topic, source snapshot, generation metadata, image candidates with attribution/license metadata, pending candidate edges, and an `ingestion_jobs` row. Topic and asset rows stay review-gated until approval.

Each generated topic also records node generation state:

- `generation_status`
- `generation_version`
- `generation_hash`
- `generation_error`

Use `--skip-cached` to avoid regenerating a topic when its local card JSON already exists:

```bash
python3 scripts/backend_ingest.py ingest "Ada Lovelace" \
  --skip-cached \
  --cards-out data/cards \
  --sql-out /tmp/wikis_ingest_ada_lovelace.sql
```

Ingestion SQL records a generation lock using `generation_locks`. Override the owner when running from a scheduled worker:

```bash
python3 scripts/backend_ingest.py ingest "Ada Lovelace" \
  --lock-owner worker-01 \
  --lock-ttl-minutes 15 \
  --execute
```

## Batch Ingest

Use one title per line:

```bash
python3 scripts/backend_ingest.py ingest \
  --titles-file data/graph/next_candidate_topics.txt \
  --source batch \
  --sql-out /tmp/wikis_batch_ingest.sql
```

Use `--execute` with `DATABASE_URL` to apply the generated SQL. Failures are recorded as failed `ingestion_jobs` statements in the SQL output so they are observable and retryable.

## Procedural Expansion From A Seed

Use `scripts/procedural_expand.py` when you want the Wikipedia Map style workflow:

```text
seed topic -> first N Wikipedia links -> generated cards -> Supabase draft rows
```

Generate a bounded local test from Black hole without using OpenAI or touching Supabase:

```bash
python3 scripts/procedural_expand.py "Black hole" \
  --condenser local \
  --links-per-topic 5 \
  --max-depth 1 \
  --max-topics 6 \
  --cards-out /tmp/wikis_procedural_cards \
  --sql-out /tmp/wikis_black_hole_expansion.sql \
  --manifest-out /tmp/wikis_black_hole_expansion.json
```

Generate OpenAI-condensed draft content and apply it to Supabase:

```bash
python3 scripts/procedural_expand.py "Black hole" \
  --condenser openai \
  --links-per-topic 5 \
  --max-depth 1 \
  --max-topics 6 \
  --execute
```

For a larger surrounding cloud, increase the distance and cap together:

```bash
python3 scripts/procedural_expand.py "Black hole" \
  --condenser openai \
  --links-per-topic 5 \
  --max-depth 2 \
  --max-topics 31 \
  --execute
```

Keep the caps conservative at first. `--links-per-topic 5 --max-depth 2` can generate up to 31 topics before duplicate filtering. Generated topics stay review-gated as draft/provisional rows until they are approved.

## Live Mobile Frontier Generation

The feed API can schedule procedural generation while the user swipes:

```http
POST /v1/feed/next
```

Request fields:

```json
{
  "currentTopicId": "black-hole",
  "gesture": "down",
  "exploredTopicIds": ["black-hole"],
  "frontierLimit": 2,
  "prefetchLimit": 3,
  "allowPrototypeContent": true,
  "liveGenerationEnabled": true,
  "liveGenerationLimit": 1
}
```

Behavior:

- The API returns the next cached/provisional topic immediately.
- It includes `backgroundIngestionTopics`, which are first-link Wikipedia candidates from the current frontier.
- If live generation is enabled, the API first claims up to `liveGenerationLimit` candidates in `ingestion_jobs`, then schedules only the claimed candidates after the response is sent.
- Repeated swipes do not call OpenAI again for a candidate that is already `queued`, `running`, or `succeeded`.
- Generated topics are stored as `needs_review` and `provisional`, but the resolver can include them when `allowPrototypeContent` is true.
- Repeated swipes grow the graph around the user's actual path instead of recursively generating a large tree from one gesture.

Production environment switches:

```bash
WIKIS_LIVE_GENERATION_ENABLED=1
WIKIS_LIVE_GENERATION_CONDENSER=openai
WIKIS_OPENAI_MODEL=gpt-5-mini
WIKIS_LIVE_CARDS_OUT=data/cards
```

Set `WIKIS_LIVE_GENERATION_ENABLED=0` to keep the endpoint traversal-only while still returning `backgroundIngestionTopics` for a separate worker.

## Supabase Graph Visualization

Export the current Supabase graph to a standalone interactive HTML file:

```bash
python3 scripts/export_supabase_graph.py \
  --out data/graph/supabase_graph.html \
  --json-out data/graph/supabase_graph.json
```

Open the HTML file in a browser. It shows:

- topic nodes from `topics`
- ungenerated pending candidate nodes from `candidate_edges`
- solid lines for `deeper` and `prerequisite` routes
- dashed lines for adjacent routes such as `neighbor`, `contrast`, `person`, and `place`
- pending candidate routes as lower-opacity edges

To highlight what one app session already explored:

```bash
python3 scripts/export_supabase_graph.py \
  --session-id "your-session-id" \
  --out data/graph/session_graph.html
```

This uses `exploration_events` to mark explored nodes and route edges in gold.

## Queue Background Frontier Expansion

Queue candidate topics from approved, ready topics without recursively expanding the graph:

```bash
python3 scripts/backend_ingest.py enqueue-frontier \
  --frontier-limit 2 \
  --max-jobs 100 \
  --sql-out /tmp/wikis_frontier_enqueue.sql
```

This queues at most `--frontier-limit` pending candidates per approved ready topic and caps the total SQL block at `--max-jobs`. Jobs are marked as `frontier` work and can be picked up by the same ingestion command using `--source background_expansion`.

## Approve Or Reject

Approve the latest generation for a topic:

```bash
python3 scripts/backend_ingest.py review approve ada-lovelace \
  --reviewer noah \
  --notes "Looks good for seed expansion" \
  --execute
```

Reject a topic:

```bash
python3 scripts/backend_ingest.py review reject ada-lovelace \
  --reviewer noah \
  --notes "Needs rewrite before publication" \
  --execute
```

Approval sets the topic and latest generation to `approved` and approves its assets. Rejection keeps the generated content out of production-visible status.

Approval also moves the node `generation_status` to `ready`; rejection moves it to `failed`.
