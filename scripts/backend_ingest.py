#!/usr/bin/env python3
"""Step 05 backend ingestion/admin CLI for Wikis.

The script keeps the ingestion runtime simple: generate deterministic SQL from a
Wikipedia title, optionally apply it with psql, and keep generated cards hidden
behind review status until approval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import sql_helpers as seed_sql
from wiki_to_card import DEFAULT_OPENAI_MODEL, build_card_output, slugify, write_card


LOCAL_PROMPT_VERSION = "step-05-local-v1"
LOCAL_PROVIDER = "local"
LOCAL_MODEL = "deterministic-wikipedia-condenser"
NODE_GENERATION_VERSION = "step-05-node-v1"
DEFAULT_LOCK_OWNER = "backend_ingest_cli"
DEFAULT_LOCK_TTL_MINUTES = 15


def source_hash(card_output: dict[str, Any]) -> str:
    payload = {
        "pageId": card_output["source"].get("pageId"),
        "revisionId": card_output["source"].get("revisionId"),
        "extract": card_output["source"].get("extract"),
        "images": card_output["image"].get("selected"),
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def stable_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def node_generation_hash(card_output: dict[str, Any]) -> str:
    return stable_hash(
        {
            "source_hash": source_hash(card_output),
            "generation": card_output.get("generation", {}),
            "card": card_output.get("card", {}),
            "quality": card_output.get("quality", {}),
            "version": NODE_GENERATION_VERSION,
        }
    )


def statement(lines: list[str]) -> str:
    return "\n".join(lines) + "\n"


def lock_statement(
    *,
    target_kind: str,
    target_id: str,
    lock_owner: str,
    ttl_minutes: int,
    generation_version: str,
    generation_hash: str,
) -> str:
    lock_key = f"{target_kind}:{target_id}"
    return statement(
        [
            "insert into generation_locks (",
            "  lock_key, target_kind, target_id, lock_owner, locked_until, generation_version, generation_hash",
            ") values (",
            f"  {seed_sql.sql_literal(lock_key)},",
            f"  {seed_sql.sql_literal(target_kind)},",
            f"  {seed_sql.sql_literal(target_id)},",
            f"  {seed_sql.sql_literal(lock_owner)},",
            f"  now() + interval '{int(ttl_minutes)} minutes',",
            f"  {seed_sql.sql_literal(generation_version)},",
            f"  {seed_sql.sql_literal(generation_hash)}",
            ") on conflict (lock_key) do update set",
            "  lock_owner = excluded.lock_owner,",
            "  locked_until = excluded.locked_until,",
            "  generation_version = excluded.generation_version,",
            "  generation_hash = excluded.generation_hash",
            "where generation_locks.locked_until < now()",
            "   or generation_locks.lock_owner = excluded.lock_owner;",
        ]
    )


def draft_topic_insert(topic_id: str, card_output: dict[str, Any]) -> str:
    source = card_output["source"]
    card = card_output["card"]
    quality = card_output["quality"]
    review_status = "auto_checked"
    quality_status = "prototype_pass"
    generation_status = "ready"
    generation_hash = node_generation_hash(card_output)
    return statement(
        [
            "insert into topics (",
            "  id, slug, title, canonical_wikipedia_title, pillar, short_explanation,",
            "  hook_type, hook_text, reading_seconds, source_confidence, quality_status,",
            "  review_status, risk_level, image_strategy, generation_status, generation_version,",
            "  generation_hash, generation_error",
            ") values (",
            f"  {seed_sql.sql_literal(topic_id)},",
            f"  {seed_sql.sql_literal(topic_id)},",
            f"  {seed_sql.sql_literal(card['title'])},",
            f"  {seed_sql.sql_literal(source.get('wikipediaTitle'))},",
            f"  {seed_sql.sql_literal(card['pillar'])},",
            f"  {seed_sql.sql_literal(card['explanation'])},",
            f"  {seed_sql.sql_literal(card['hookType'])},",
            f"  {seed_sql.sql_literal(card['hook'])},",
            f"  {seed_sql.sql_literal(card['readingSeconds'])},",
            "  0.800,",
            f"  {seed_sql.sql_literal(quality_status)},",
            f"  {seed_sql.sql_literal(review_status)},",
            "  'low',",
            f"  {seed_sql.sql_literal(card_output['image'].get('strategy', 'pillar_background'))},",
            f"  {seed_sql.sql_literal(generation_status)},",
            f"  {seed_sql.sql_literal(NODE_GENERATION_VERSION)},",
            f"  {seed_sql.sql_literal(generation_hash)},",
            f"  {seed_sql.sql_literal('; '.join(quality.get('issues', [])) if quality.get('issues') else None)}",
            ") on conflict (id) do update set",
            "  title = excluded.title,",
            "  canonical_wikipedia_title = excluded.canonical_wikipedia_title,",
            "  pillar = excluded.pillar,",
            "  short_explanation = excluded.short_explanation,",
            "  hook_type = excluded.hook_type,",
            "  hook_text = excluded.hook_text,",
            "  reading_seconds = excluded.reading_seconds,",
            "  source_confidence = excluded.source_confidence,",
            "  quality_status = excluded.quality_status,",
            "  review_status = excluded.review_status,",
            "  risk_level = excluded.risk_level,",
            "  image_strategy = excluded.image_strategy,",
            "  generation_status = excluded.generation_status,",
            "  generation_version = excluded.generation_version,",
            "  generation_hash = excluded.generation_hash,",
            "  generation_error = excluded.generation_error;",
        ]
    )


def snapshot_insert(topic_id: str, card_output: dict[str, Any]) -> tuple[str, str]:
    source = card_output["source"]
    image_candidates = card_output["image"].get("candidates", [])
    hash_value = source_hash(card_output)
    snapshot_id = seed_sql.stable_uuid("topic_source_snapshot", topic_id, hash_value)
    return snapshot_id, statement(
        [
            "insert into topic_source_snapshots (",
            "  id, topic_id, source_kind, wikipedia_title, wikipedia_page_id, wikipedia_revision_id,",
            "  raw_extract, lead_html, image_candidates_json,",
            "  fetched_at, source_hash",
            ") values (",
            f"  {seed_sql.uuid_literal(snapshot_id)},",
            f"  {seed_sql.sql_literal(topic_id)},",
            "  'wikipedia',",
            f"  {seed_sql.sql_literal(source.get('wikipediaTitle'))},",
            f"  {seed_sql.sql_literal(source.get('pageId'))},",
            f"  {seed_sql.sql_literal(source.get('revisionId'))},",
            f"  {seed_sql.sql_literal(source.get('extract'))},",
            f"  {seed_sql.sql_literal(source.get('leadHtml'))},",
            f"  {seed_sql.jsonb_literal(image_candidates)},",
            f"  {seed_sql.timestamptz_literal(source.get('fetchedAt'))},",
            f"  {seed_sql.sql_literal(hash_value)}",
            ") on conflict (topic_id, source_kind, source_hash) do update set",
            "  wikipedia_title = excluded.wikipedia_title,",
            "  wikipedia_page_id = excluded.wikipedia_page_id,",
            "  wikipedia_revision_id = excluded.wikipedia_revision_id,",
            "  raw_extract = excluded.raw_extract,",
            "  lead_html = excluded.lead_html,",
            "  image_candidates_json = excluded.image_candidates_json,",
            "  fetched_at = excluded.fetched_at;",
        ]
    )


def generation_insert(topic_id: str, snapshot_id: str, card_output: dict[str, Any]) -> str:
    card = card_output["card"]
    quality = card_output["quality"]
    generation = card_output.get("generation", {})
    provider = generation.get("provider", LOCAL_PROVIDER)
    model = generation.get("model", LOCAL_MODEL)
    prompt_version = generation.get("promptVersion", LOCAL_PROMPT_VERSION)
    generation_id = seed_sql.stable_uuid("llm_card_generation", topic_id, snapshot_id, provider, model, prompt_version)
    grounding_status = "flagged" if quality.get("issues") else "passed"
    generation_quality_status = "prototype_pass"
    return statement(
        [
            "insert into llm_card_generations (",
            "  id, topic_id, source_snapshot_id, provider, model, prompt_version,",
            "  generated_title, generated_pillar, generated_explanation, generated_hook_type,",
            "  generated_hook_text, confidence_notes_json,",
            "  grounding_status, quality_status, reviewer_notes",
            ") values (",
            f"  {seed_sql.uuid_literal(generation_id)},",
            f"  {seed_sql.sql_literal(topic_id)},",
            f"  {seed_sql.uuid_literal(snapshot_id)},",
            f"  {seed_sql.sql_literal(provider)},",
            f"  {seed_sql.sql_literal(model)},",
            f"  {seed_sql.sql_literal(prompt_version)},",
            f"  {seed_sql.sql_literal(card['title'])},",
            f"  {seed_sql.sql_literal(card['pillar'])},",
            f"  {seed_sql.sql_literal(card['explanation'])},",
            f"  {seed_sql.sql_literal(card['hookType'])},",
            f"  {seed_sql.sql_literal(card['hook'])},",
            f"  {seed_sql.jsonb_literal(card.get('confidenceNotes', []))},",
            f"  {seed_sql.sql_literal(grounding_status)},",
            f"  {seed_sql.sql_literal(generation_quality_status)},",
            f"  {seed_sql.sql_literal('; '.join(quality.get('issues', [])) if quality.get('issues') else None)}",
            ") on conflict (id) do update set",
            "  generated_title = excluded.generated_title,",
            "  generated_pillar = excluded.generated_pillar,",
            "  generated_explanation = excluded.generated_explanation,",
            "  generated_hook_type = excluded.generated_hook_type,",
            "  generated_hook_text = excluded.generated_hook_text,",
            "  confidence_notes_json = excluded.confidence_notes_json,",
            "  grounding_status = excluded.grounding_status,",
            "  quality_status = excluded.quality_status,",
            "  reviewer_notes = excluded.reviewer_notes;",
        ]
    )


def image_statements(topic_id: str, card_output: dict[str, Any]) -> list[str]:
    image = card_output["image"]
    selected = image.get("selected")
    output: list[str] = []
    for candidate in image.get("candidates", []):
        if not candidate.get("url"):
            continue
        candidate_id = seed_sql.stable_uuid("image_candidate", topic_id, candidate.get("url"))
        license_name = candidate.get("license") or "unverified_wikimedia_license"
        attribution = candidate.get("attribution") or candidate.get("title") or candidate.get("source")
        output.append(
            statement(
                [
                    "insert into image_candidates (",
                    "  id, topic_id, source, source_title, url, thumbnail_url, width, height,",
                    "  license, attribution, media_type, quality_score, rejection_reason, selected",
                    ") values (",
                    f"  {seed_sql.uuid_literal(candidate_id)},",
                    f"  {seed_sql.sql_literal(topic_id)},",
                    f"  {seed_sql.sql_literal(candidate.get('source', 'wikipedia'))},",
                    f"  {seed_sql.sql_literal(candidate.get('title'))},",
                    f"  {seed_sql.sql_literal(candidate.get('url'))},",
                    f"  {seed_sql.sql_literal(candidate.get('thumbnailUrl'))},",
                    f"  {seed_sql.sql_literal(candidate.get('width'))},",
                    f"  {seed_sql.sql_literal(candidate.get('height'))},",
                    f"  {seed_sql.sql_literal(license_name)},",
                    f"  {seed_sql.sql_literal(attribution)},",
                    "  'image',",
                    f"  {seed_sql.sql_literal(candidate.get('qualityScore'))},",
                    f"  {seed_sql.sql_literal('; '.join(candidate.get('rejectionReasons', [])) if candidate.get('rejectionReasons') else None)},",
                    f"  {seed_sql.sql_literal(selected is not None and candidate.get('url') == selected.get('url'))}",
                    ") on conflict (topic_id, url) do update set",
                    "  source = excluded.source,",
                    "  source_title = excluded.source_title,",
                    "  thumbnail_url = excluded.thumbnail_url,",
                    "  width = excluded.width,",
                    "  height = excluded.height,",
                    "  license = excluded.license,",
                    "  attribution = excluded.attribution,",
                    "  quality_score = excluded.quality_score,",
                    "  rejection_reason = excluded.rejection_reason,",
                    "  selected = excluded.selected;",
                ]
            )
        )

    if not selected:
        asset_id = seed_sql.stable_uuid("topic_asset", topic_id, "pillar_background")
        output.extend([
            seed_sql.asset_insert(
                asset_id=asset_id,
                topic_id=topic_id,
                pillar=image.get("fallbackPillar") or card_output["card"]["pillar"],
                image_candidate_id=None,
                asset_type="pillar_background",
                url=None,
                thumbnail_url=None,
                attribution="Wikis generated pillar background",
                license_name="internal",
                quality_score=None,
            ),
            statement(
                [
                    "update topics",
                    f"set image_asset_id = {seed_sql.uuid_literal(asset_id)}",
                    f"where id = {seed_sql.sql_literal(topic_id)};",
                ]
            ),
        ])
        return output

    candidate_id = seed_sql.stable_uuid("image_candidate", topic_id, selected.get("url"))
    asset_id = seed_sql.stable_uuid("topic_asset", topic_id, "wikipedia_image")
    license_name = selected.get("license") or "unverified_wikimedia_license"
    attribution = selected.get("attribution") or selected.get("title") or selected.get("source")
    output.extend([
        seed_sql.asset_insert(
            asset_id=asset_id,
            topic_id=topic_id,
            pillar=None,
            image_candidate_id=candidate_id,
            asset_type="wikipedia_image",
            url=selected.get("url"),
            thumbnail_url=selected.get("thumbnailUrl"),
            attribution=attribution,
            license_name=license_name,
            quality_score=selected.get("qualityScore"),
        ).replace("  true\n", "  false\n"),
        statement(
            [
                "update topics",
                f"set image_asset_id = {seed_sql.uuid_literal(asset_id)}",
                f"where id = {seed_sql.sql_literal(topic_id)};",
            ]
        ),
    ])
    return output


def job_statement(
    title: str,
    source: str,
    status: str,
    *,
    topic_id: str | None = None,
    error: str | None = None,
    lock_owner: str | None = None,
    ttl_minutes: int | None = None,
    generation_version: str | None = None,
    generation_hash: str | None = None,
) -> str:
    locked_until = f"now() + interval '{int(ttl_minutes)} minutes'" if lock_owner and ttl_minutes else "null"
    return statement(
        [
            "insert into ingestion_jobs (",
            "  requested_title, normalized_title, topic_id, source, status, attempts, last_error,",
            "  started_at, finished_at, lock_owner, locked_until, generation_version, generation_hash",
            ")",
            "values (",
            f"  {seed_sql.sql_literal(title)},",
            f"  {seed_sql.sql_literal(title)},",
            f"  {seed_sql.sql_literal(topic_id)},",
            f"  {seed_sql.sql_literal(source)},",
            f"  {seed_sql.sql_literal(status)},",
            "  1,",
            f"  {seed_sql.sql_literal(error)},",
            "  now(),",
            "  now(),",
            f"  {seed_sql.sql_literal(lock_owner)},",
            f"  {locked_until},",
            f"  {seed_sql.sql_literal(generation_version)},",
            f"  {seed_sql.sql_literal(generation_hash)}",
            ") on conflict (requested_title, source) do update set",
            "  normalized_title = excluded.normalized_title,",
            "  topic_id = excluded.topic_id,",
            "  status = excluded.status,",
            "  attempts = ingestion_jobs.attempts + 1,",
            "  last_error = excluded.last_error,",
            "  started_at = excluded.started_at,",
            "  finished_at = excluded.finished_at,",
            "  lock_owner = excluded.lock_owner,",
            "  locked_until = excluded.locked_until,",
            "  generation_version = excluded.generation_version,",
            "  generation_hash = excluded.generation_hash;",
        ]
    )


def ingest_sql(
    title: str,
    source: str,
    cards_out: Path | None,
    condenser: str,
    openai_model: str | None,
    lock_owner: str,
    lock_ttl_minutes: int,
    topic_id_override: str | None = None,
    include_images: bool = True,
) -> tuple[str, str]:
    card_output = build_card_output(title, condenser=condenser, model=openai_model, include_images=include_images)
    return card_output_sql(
        title,
        source,
        cards_out,
        card_output,
        lock_owner,
        lock_ttl_minutes,
        topic_id_override=topic_id_override,
    )


def card_output_sql(
    title: str,
    source: str,
    cards_out: Path | None,
    card_output: dict[str, Any],
    lock_owner: str,
    lock_ttl_minutes: int,
    topic_id_override: str | None = None,
) -> tuple[str, str]:
    topic_id = topic_id_override or slugify(card_output["source"]["wikipediaTitle"])
    generation_hash = node_generation_hash(card_output)
    if cards_out:
        write_card(cards_out, card_output)

    snapshot_id, snapshot_sql = snapshot_insert(topic_id, card_output)
    statements = [
        "begin;",
        lock_statement(
            target_kind="node",
            target_id=topic_id,
            lock_owner=lock_owner,
            ttl_minutes=lock_ttl_minutes,
            generation_version=NODE_GENERATION_VERSION,
            generation_hash=generation_hash,
        ),
        job_statement(
            title,
            source,
            "running",
            topic_id=topic_id,
            lock_owner=lock_owner,
            ttl_minutes=lock_ttl_minutes,
            generation_version=NODE_GENERATION_VERSION,
            generation_hash=generation_hash,
        ),
        snapshot_sql,
        generation_insert(topic_id, snapshot_id, card_output),
        *image_statements(topic_id, card_output),
        job_statement(
            title,
            source,
            "succeeded",
            topic_id=topic_id,
            generation_version=NODE_GENERATION_VERSION,
            generation_hash=generation_hash,
        ),
        "commit;",
    ]
    statements.insert(2, draft_topic_insert(topic_id, card_output))
    return topic_id, "\n".join(statements) + "\n"


def skipped_sql(title: str, source: str, cards_out: Path | None) -> tuple[str, str]:
    topic_id = slugify(title)
    if cards_out:
        path = cards_out / f"{topic_id}.json"
        if path.exists():
            try:
                card_output = json.loads(path.read_text(encoding="utf-8"))
                topic_id = slugify(card_output["source"]["wikipediaTitle"])
            except Exception:
                pass
    sql = "\n".join(
        [
            "begin;",
            job_statement(
                title,
                source,
                "skipped",
                topic_id=topic_id,
                generation_version=NODE_GENERATION_VERSION,
                generation_hash=None,
            ),
            "commit;",
        ]
    ) + "\n"
    return topic_id, sql


def review_sql(topic_id: str, action: str, reviewer: str | None, notes: str | None) -> str:
    if action == "approve":
        topic_status = "approved"
        generation_status = "approved"
        review_status = "approved"
    else:
        topic_status = "rejected"
        generation_status = "rejected"
        review_status = "rejected"

    return statement(
        [
            "begin;",
            "insert into ingestion_review_events (topic_id, generation_id, action, reviewer, notes)",
            "values (",
            f"  {seed_sql.sql_literal(topic_id)},",
            "  (select id from llm_card_generations",
            f"   where topic_id = {seed_sql.sql_literal(topic_id)}",
            "   order by created_at desc limit 1),",
            f"  {seed_sql.sql_literal(action)},",
            f"  {seed_sql.sql_literal(reviewer)},",
            f"  {seed_sql.sql_literal(notes)}",
            ");",
            "update topics",
            f"set quality_status = {seed_sql.sql_literal(topic_status)}, review_status = {seed_sql.sql_literal(review_status)},",
            f"    generation_status = {seed_sql.sql_literal('ready' if action == 'approve' else 'failed')}",
            f"where id = {seed_sql.sql_literal(topic_id)};",
            "update llm_card_generations",
            f"set quality_status = {seed_sql.sql_literal(generation_status)}",
            "where id = (",
            "  select id from llm_card_generations",
            f"  where topic_id = {seed_sql.sql_literal(topic_id)}",
            "  order by created_at desc limit 1",
            ");",
            "update topic_assets",
            f"set approved = {seed_sql.sql_literal(action == 'approve')}",
            f"where topic_id = {seed_sql.sql_literal(topic_id)};",
            "commit;",
        ]
    )


def psql_execute(database_url: str, sql: str) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False, encoding="utf-8") as handle:
        handle.write(sql)
        path = handle.name
    try:
        subprocess.run(["psql", database_url, "-v", "ON_ERROR_STOP=1", "-f", path], check=True)
    finally:
        Path(path).unlink(missing_ok=True)


def write_or_execute(sql: str, out: Path | None, database_url: str | None, execute: bool) -> None:
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(sql, encoding="utf-8")
        print(f"wrote {out}")
    if execute:
        if not database_url:
            raise RuntimeError("--execute requires --database-url or DATABASE_URL")
        psql_execute(database_url, sql)


def titles_from_args(args: argparse.Namespace) -> list[str]:
    titles = list(args.titles)
    if args.titles_file:
        titles.extend(
            line.strip()
            for line in args.titles_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        )
    return titles


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Wikis Step 05 backend ingestion/admin tasks.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest = subparsers.add_parser("ingest", help="Ingest one or more Wikipedia titles into draft review SQL.")
    ingest.add_argument("titles", nargs="*")
    ingest.add_argument("--titles-file", type=Path)
    ingest.add_argument("--cards-out", type=Path)
    ingest.add_argument("--sql-out", type=Path)
    ingest.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    ingest.add_argument("--execute", action="store_true")
    ingest.add_argument("--source", choices=["manual", "batch"], default="manual")
    ingest.add_argument("--delay", type=float, default=1.0)
    ingest.add_argument("--condenser", choices=["local", "openai"], default="local")
    ingest.add_argument("--openai-model", default=os.environ.get("WIKIS_OPENAI_MODEL", DEFAULT_OPENAI_MODEL))
    ingest.add_argument("--skip-cached", action="store_true", help="Skip titles whose local card JSON already exists.")
    ingest.add_argument("--lock-owner", default=os.environ.get("WIKIS_INGEST_LOCK_OWNER", DEFAULT_LOCK_OWNER))
    ingest.add_argument("--lock-ttl-minutes", type=int, default=DEFAULT_LOCK_TTL_MINUTES)
    ingest.add_argument("--no-images", action="store_true", help="Use pillar backgrounds instead of fetching Wikipedia image metadata.")

    review = subparsers.add_parser("review", help="Approve or reject a generated topic.")
    review.add_argument("action", choices=["approve", "reject"])
    review.add_argument("topic_id")
    review.add_argument("--reviewer")
    review.add_argument("--notes")
    review.add_argument("--sql-out", type=Path)
    review.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    review.add_argument("--execute", action="store_true")

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "review":
        sql = review_sql(args.topic_id, args.action, args.reviewer, args.notes)
        write_or_execute(sql, args.sql_out, args.database_url, args.execute)
        print(f"{args.action} SQL ready for {args.topic_id}")
        return 0
    titles = titles_from_args(args)
    if not titles:
        print("ERROR: provide at least one title or --titles-file", file=sys.stderr)
        return 2

    sql_blocks: list[str] = []
    failures = 0
    for index, title in enumerate(titles):
        try:
            cached_path = args.cards_out / f"{slugify(title)}.json" if args.cards_out else None
            if args.skip_cached and cached_path and cached_path.exists():
                topic_id, sql = skipped_sql(title, args.source, args.cards_out)
                sql_blocks.append(sql)
                print(f"{title} -> {topic_id} (skipped cached)")
            else:
                topic_id, sql = ingest_sql(
                    title,
                    args.source,
                    args.cards_out,
                    args.condenser,
                    args.openai_model,
                    args.lock_owner,
                    args.lock_ttl_minutes,
                    include_images=not args.no_images,
                )
                sql_blocks.append(sql)
                print(f"{title} -> {topic_id} (prototype_pass)")
        except Exception as exc:  # noqa: BLE001 - batch ingestion should continue.
            failures += 1
            sql_blocks.append(statement(["begin;", job_statement(title, args.source, "failed", error=str(exc), generation_version=NODE_GENERATION_VERSION), "commit;"]))
            print(f"ERROR: {title}: {exc}", file=sys.stderr)
        if index < len(titles) - 1 and args.delay > 0:
            time.sleep(args.delay)

    write_or_execute("\n".join(sql_blocks), args.sql_out, args.database_url, args.execute)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
