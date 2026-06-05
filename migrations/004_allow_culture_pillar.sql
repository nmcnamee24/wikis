-- Allow the Step 05 content engine to use the culture pillar while preserving
-- existing seed data that still uses literature.
-- Apply with: psql "$DATABASE_URL" -f migrations/004_allow_culture_pillar.sql

begin;

alter table topics
  drop constraint if exists topics_pillar_check,
  add constraint topics_pillar_check
    check (pillar in ('science', 'literature', 'culture', 'society', 'history'));

alter table llm_card_generations
  drop constraint if exists llm_card_generations_generated_pillar_check,
  add constraint llm_card_generations_generated_pillar_check
    check (generated_pillar in ('science', 'literature', 'culture', 'society', 'history'));

alter table topic_assets
  drop constraint if exists topic_assets_pillar_check,
  add constraint topic_assets_pillar_check
    check (pillar is null or pillar in ('science', 'literature', 'culture', 'society', 'history'));

commit;
