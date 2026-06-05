-- Wikis Step 05 ingestion workflow state.
-- Apply with: psql "$DATABASE_URL" -f migrations/003_ingestion_workflow.sql

begin;

create table if not exists ingestion_jobs (
  id uuid primary key default gen_random_uuid(),
  requested_title text not null,
  normalized_title text,
  topic_id text references topics(id) on delete set null,
  source text not null default 'manual' check (source in ('manual', 'batch', 'candidate_queue', 'background_expansion')),
  priority integer not null default 100,
  status text not null default 'queued' check (
    status in ('queued', 'running', 'succeeded', 'failed', 'skipped', 'retryable')
  ),
  attempts integer not null default 0 check (attempts >= 0),
  last_error text,
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (requested_title, source)
);

create table if not exists ingestion_review_events (
  id uuid primary key default gen_random_uuid(),
  topic_id text not null references topics(id) on delete cascade,
  generation_id uuid references llm_card_generations(id) on delete set null,
  action text not null check (action in ('approve', 'reject', 'needs_changes')),
  reviewer text,
  notes text,
  created_at timestamptz not null default now()
);

create index if not exists ingestion_jobs_status_priority_idx
  on ingestion_jobs(status, priority desc, created_at);
create index if not exists ingestion_jobs_topic_idx on ingestion_jobs(topic_id);
create index if not exists ingestion_review_events_topic_created_idx
  on ingestion_review_events(topic_id, created_at desc);

drop trigger if exists ingestion_jobs_set_updated_at on ingestion_jobs;
create trigger ingestion_jobs_set_updated_at before update on ingestion_jobs
for each row execute function set_updated_at();

commit;
