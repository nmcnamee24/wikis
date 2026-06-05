-- Wikis Step 05 node/edge generation state, idempotency, locks, and frontier caps.
-- Apply with: psql "$DATABASE_URL" -f migrations/005_ingestion_generation_state.sql

begin;

alter table topics
  add column if not exists generation_status text not null default 'missing',
  add column if not exists generation_version text,
  add column if not exists generation_hash text,
  add column if not exists generation_error text;

alter table topics
  drop constraint if exists topics_generation_status_check,
  add constraint topics_generation_status_check
    check (generation_status in ('missing', 'provisional', 'generating', 'ready', 'failed'));

alter table topic_edges
  add column if not exists rank integer,
  add column if not exists confidence numeric(4, 3),
  add column if not exists source_evidence text,
  add column if not exists generation_status text not null default 'missing',
  add column if not exists generation_version text,
  add column if not exists generation_hash text,
  add column if not exists generation_error text;

alter table topic_edges
  drop constraint if exists topic_edges_generation_status_check,
  add constraint topic_edges_generation_status_check
    check (generation_status in ('missing', 'provisional', 'generating', 'ready', 'failed'));

alter table ingestion_jobs
  add column if not exists job_kind text not null default 'node',
  add column if not exists lock_owner text,
  add column if not exists locked_until timestamptz,
  add column if not exists frontier_depth integer not null default 0,
  add column if not exists frontier_limit integer not null default 2,
  add column if not exists generation_version text,
  add column if not exists generation_hash text;

alter table ingestion_jobs
  drop constraint if exists ingestion_jobs_job_kind_check,
  add constraint ingestion_jobs_job_kind_check
    check (job_kind in ('node', 'edge', 'frontier'));

alter table ingestion_jobs
  drop constraint if exists ingestion_jobs_frontier_depth_check,
  add constraint ingestion_jobs_frontier_depth_check
    check (frontier_depth >= 0);

alter table ingestion_jobs
  drop constraint if exists ingestion_jobs_frontier_limit_check,
  add constraint ingestion_jobs_frontier_limit_check
    check (frontier_limit between 0 and 20);

create table if not exists generation_locks (
  lock_key text primary key,
  target_kind text not null check (target_kind in ('node', 'edge', 'frontier')),
  target_id text not null,
  lock_owner text not null,
  locked_until timestamptz not null,
  generation_version text,
  generation_hash text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists topics_generation_status_idx
  on topics(generation_status, quality_status);
create index if not exists topic_edges_generation_status_idx
  on topic_edges(generation_status, from_topic_id, rank);
create index if not exists ingestion_jobs_lock_idx
  on ingestion_jobs(status, locked_until);
create index if not exists generation_locks_target_idx
  on generation_locks(target_kind, target_id);

update topics
set generation_status = case
    when quality_status in ('approved', 'prototype_pass') then 'ready'
    when quality_status = 'needs_review' then 'provisional'
    when quality_status = 'rejected' then 'failed'
    else generation_status
  end,
  generation_version = coalesce(generation_version, 'step-02-seed-backfill')
where generation_status = 'missing';

update topic_edges
set generation_status = case
    when status = 'approved' then 'ready'
    else generation_status
  end,
  generation_version = coalesce(generation_version, 'step-02-seed-backfill'),
  rank = coalesce(rank, 1),
  confidence = coalesce(confidence, strength)
where generation_status = 'missing';

drop trigger if exists generation_locks_set_updated_at on generation_locks;
create trigger generation_locks_set_updated_at before update on generation_locks
for each row execute function set_updated_at();

commit;
