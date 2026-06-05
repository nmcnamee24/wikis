-- Enable RLS on public-schema tables used by Wikis.
--
-- The current app accesses these tables through the Railway API using a server
-- Postgres connection. No anon/authenticated Data API policies are granted yet;
-- client-visible access should be added deliberately when the native app moves
-- from the server API to direct Supabase client calls.

begin;

alter table topics enable row level security;
alter table topic_source_snapshots enable row level security;
alter table llm_card_generations enable row level security;
alter table image_candidates enable row level security;
alter table topic_assets enable row level security;
alter table topic_edges enable row level security;
alter table candidate_edges enable row level security;
alter table app_users enable row level security;
alter table exploration_events enable row level security;
alter table saved_topics enable row level security;
alter table ingestion_jobs enable row level security;
alter table ingestion_review_events enable row level security;
alter table generation_locks enable row level security;

commit;
