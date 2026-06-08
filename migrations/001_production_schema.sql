-- Wikis production data model.
-- Apply with: psql "$DATABASE_URL" -f migrations/001_production_schema.sql

begin;

create extension if not exists pgcrypto;

create or replace function set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table if not exists topics (
  id text primary key,
  slug text not null unique,
  title text not null,
  canonical_wikipedia_title text,
  wikidata_id text,
  pillar text not null check (pillar in ('science', 'literature', 'society', 'history')),
  short_explanation text not null,
  hook_type text not null,
  hook_text text not null,
  reading_seconds integer not null check (reading_seconds > 0),
  source_confidence numeric(4, 3) check (source_confidence is null or source_confidence between 0 and 1),
  quality_status text not null default 'draft' check (
    quality_status in ('draft', 'prototype_pass', 'needs_review', 'approved', 'rejected', 'archived')
  ),
  review_status text not null default 'unreviewed' check (
    review_status in ('unreviewed', 'auto_checked', 'human_reviewed', 'approved', 'rejected')
  ),
  risk_level text not null default 'low' check (risk_level in ('low', 'medium', 'high')),
  image_strategy text not null default 'pillar_background' check (
    image_strategy in ('wikipedia_image', 'pillar_background', 'custom_asset')
  ),
  image_asset_id uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists topic_source_snapshots (
  id uuid primary key default gen_random_uuid(),
  topic_id text not null references topics(id) on delete cascade,
  source_kind text not null default 'wikipedia' check (source_kind in ('wikipedia', 'wikidata', 'external')),
  wikipedia_title text not null,
  wikipedia_page_id bigint,
  wikipedia_revision_id bigint,
  raw_extract text,
  lead_html text,
  image_candidates_json jsonb not null default '[]'::jsonb,
  fetched_at timestamptz,
  source_hash text not null,
  created_at timestamptz not null default now(),
  unique (topic_id, source_kind, source_hash)
);

create table if not exists llm_card_generations (
  id uuid primary key default gen_random_uuid(),
  topic_id text not null references topics(id) on delete cascade,
  source_snapshot_id uuid not null references topic_source_snapshots(id) on delete restrict,
  provider text not null,
  model text not null,
  prompt_version text not null,
  generated_title text not null,
  generated_pillar text not null check (generated_pillar in ('science', 'literature', 'society', 'history')),
  generated_explanation text not null,
  generated_hook_type text not null,
  generated_hook_text text not null,
  confidence_notes_json jsonb not null default '[]'::jsonb,
  grounding_status text not null default 'unchecked' check (
    grounding_status in ('unchecked', 'passed', 'flagged', 'failed')
  ),
  quality_status text not null default 'draft' check (
    quality_status in ('draft', 'prototype_pass', 'needs_review', 'approved', 'rejected')
  ),
  reviewer_notes text,
  created_at timestamptz not null default now()
);

create table if not exists image_candidates (
  id uuid primary key default gen_random_uuid(),
  topic_id text not null references topics(id) on delete cascade,
  source text not null,
  source_title text,
  url text not null,
  thumbnail_url text,
  width integer check (width is null or width > 0),
  height integer check (height is null or height > 0),
  license text,
  attribution text,
  media_type text not null default 'image',
  quality_score numeric(4, 3) check (quality_score is null or quality_score between 0 and 1),
  rejection_reason text,
  selected boolean not null default false,
  created_at timestamptz not null default now(),
  unique (topic_id, url)
);

create table if not exists topic_assets (
  id uuid primary key default gen_random_uuid(),
  topic_id text references topics(id) on delete cascade,
  pillar text check (pillar is null or pillar in ('science', 'literature', 'society', 'history')),
  image_candidate_id uuid references image_candidates(id) on delete set null,
  asset_type text not null check (asset_type in ('wikipedia_image', 'pillar_background', 'custom_image')),
  url text,
  thumbnail_url text,
  storage_key text,
  attribution text,
  license text,
  quality_score numeric(4, 3) check (quality_score is null or quality_score between 0 and 1),
  approved boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (topic_id is not null or pillar is not null)
);

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'topics_image_asset_id_fkey'
  ) then
    alter table topics
      add constraint topics_image_asset_id_fkey
      foreign key (image_asset_id) references topic_assets(id) on delete set null;
  end if;
end;
$$;

create table if not exists topic_edges (
  id uuid primary key default gen_random_uuid(),
  from_topic_id text not null references topics(id) on delete cascade,
  to_topic_id text not null references topics(id) on delete cascade,
  edge_type text not null check (
    edge_type in ('deeper', 'neighbor', 'teleport', 'prerequisite', 'contrast', 'person', 'place')
  ),
  strength numeric(4, 3) not null check (strength between 0 and 1),
  reason text not null,
  status text not null default 'approved' check (status in ('approved', 'disabled', 'archived')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (from_topic_id <> to_topic_id),
  unique (from_topic_id, to_topic_id, edge_type)
);

create table if not exists app_users (
  id uuid primary key default gen_random_uuid(),
  identity_kind text not null default 'anonymous' check (identity_kind in ('anonymous', 'account')),
  external_subject text unique,
  display_name text,
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (
    (identity_kind = 'anonymous' and external_subject is null)
    or (identity_kind = 'account' and external_subject is not null)
  )
);

create table if not exists exploration_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references app_users(id) on delete set null,
  anonymous_session_id text,
  session_id text not null,
  from_topic_id text references topics(id) on delete set null,
  to_topic_id text references topics(id) on delete set null,
  gesture text not null check (gesture in ('start', 'down', 'right', 'left', 'back', 'save', 'unsave')),
  reason_code text,
  dwell_ms integer check (dwell_ms is null or dwell_ms >= 0),
  saved boolean not null default false,
  client_event_at timestamptz,
  created_at timestamptz not null default now(),
  check (user_id is not null or anonymous_session_id is not null)
);

create table if not exists saved_topics (
  user_id uuid not null references app_users(id) on delete cascade,
  topic_id text not null references topics(id) on delete cascade,
  saved_at timestamptz not null default now(),
  source_event_id uuid references exploration_events(id) on delete set null,
  primary key (user_id, topic_id)
);

create index if not exists topic_source_snapshots_topic_idx on topic_source_snapshots(topic_id);
create index if not exists llm_card_generations_topic_idx on llm_card_generations(topic_id);
create index if not exists image_candidates_topic_selected_idx on image_candidates(topic_id, selected);
create index if not exists topic_assets_topic_idx on topic_assets(topic_id);
create index if not exists topic_edges_from_type_idx on topic_edges(from_topic_id, edge_type, strength desc);
create index if not exists topic_edges_to_idx on topic_edges(to_topic_id);
create index if not exists exploration_events_user_created_idx on exploration_events(user_id, created_at desc);
create index if not exists exploration_events_session_created_idx on exploration_events(session_id, created_at desc);
create index if not exists saved_topics_topic_idx on saved_topics(topic_id);

drop trigger if exists topics_set_updated_at on topics;
create trigger topics_set_updated_at before update on topics
for each row execute function set_updated_at();

drop trigger if exists topic_assets_set_updated_at on topic_assets;
create trigger topic_assets_set_updated_at before update on topic_assets
for each row execute function set_updated_at();

drop trigger if exists topic_edges_set_updated_at on topic_edges;
create trigger topic_edges_set_updated_at before update on topic_edges
for each row execute function set_updated_at();

drop trigger if exists app_users_set_updated_at on app_users;
create trigger app_users_set_updated_at before update on app_users
for each row execute function set_updated_at();

commit;
