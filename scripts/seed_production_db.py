#!/usr/bin/env python3
"""Generate or apply SQL that seeds the production database from Step 02 data."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any


NAMESPACE = uuid.UUID("73fffd0f-a939-5cde-a1b5-6f95fda56f10")


def slugify(value: str) -> str:
    value = value.lower().replace("&", " and ")
    value = re.sub(r"\([^)]*\)", "", value)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "topic"


def stable_uuid(*parts: object) -> str:
    return str(uuid.uuid5(NAMESPACE, ":".join(str(part) for part in parts)))


def sql_literal(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def jsonb_literal(value: object) -> str:
    return f"{sql_literal(json.dumps(value, ensure_ascii=False, sort_keys=True))}::jsonb"


def timestamptz_literal(value: object) -> str:
    return f"{sql_literal(value)}::timestamptz" if value else "null"


def uuid_literal(value: str | None) -> str:
    return f"{sql_literal(value)}::uuid" if value else "null"


def load_cards(cards_dir: Path) -> dict[str, dict[str, Any]]:
    cards: dict[str, dict[str, Any]] = {}
    for path in sorted(cards_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        source = data["source"]
        cards[slugify(source["wikipediaTitle"])] = data
    return cards


def source_hash(source: dict[str, Any], mapping: dict[str, Any]) -> str:
    payload = {
        "pageId": source.get("pageId"),
        "revisionId": source.get("revisionId"),
        "extract": source.get("extract"),
        "firstParagraph": source.get("firstParagraph"),
        "links": mapping.get("leadOrFallbackLinks") or mapping.get("firstParagraphLinks") or [],
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def statement(lines: list[str]) -> str:
    return "\n".join(lines) + "\n"


def topic_insert(topic: dict[str, Any]) -> str:
    return statement(
        [
            "insert into topics (",
            "  id, slug, title, canonical_wikipedia_title, pillar, short_explanation,",
            "  hook_type, hook_text, reading_seconds, source_confidence, quality_status,",
            "  review_status, risk_level, image_strategy",
            ") values (",
            f"  {sql_literal(topic['id'])},",
            f"  {sql_literal(topic['id'])},",
            f"  {sql_literal(topic['title'])},",
            f"  {sql_literal(topic.get('wikipedia', {}).get('title'))},",
            f"  {sql_literal(topic['pillar'])},",
            f"  {sql_literal(topic['explanation'])},",
            f"  {sql_literal(topic['hookType'])},",
            f"  {sql_literal(topic['hook'])},",
            f"  {sql_literal(topic['readingSeconds'])},",
            "  0.800,",
            f"  {sql_literal(topic.get('qualityStatus', 'prototype_pass'))},",
            "  'auto_checked',",
            "  'low',",
            f"  {sql_literal(topic.get('image', {}).get('strategy', 'pillar_background'))}",
            ") on conflict (id) do update set",
            "  slug = excluded.slug,",
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
            "  image_strategy = excluded.image_strategy;",
        ]
    )


def snapshot_insert(topic_id: str, card_data: dict[str, Any]) -> tuple[str, str]:
    source = card_data["source"]
    mapping = card_data.get("mapping", {})
    image = card_data.get("image", {})
    hash_value = source_hash(source, mapping)
    snapshot_id = stable_uuid("topic_source_snapshot", topic_id, hash_value)
    link_candidates = mapping.get("leadOrFallbackLinks") or mapping.get("firstParagraphLinks") or []
    image_candidates = [image["selected"]] if image.get("selected") else []
    sql = statement(
        [
            "insert into topic_source_snapshots (",
            "  id, topic_id, source_kind, wikipedia_title, wikipedia_page_id, wikipedia_revision_id,",
            "  raw_extract, first_paragraph, link_candidates_json, image_candidates_json,",
            "  fetched_at, source_hash",
            ") values (",
            f"  {uuid_literal(snapshot_id)},",
            f"  {sql_literal(topic_id)},",
            "  'wikipedia',",
            f"  {sql_literal(source.get('wikipediaTitle'))},",
            f"  {sql_literal(source.get('pageId'))},",
            f"  {sql_literal(source.get('revisionId'))},",
            f"  {sql_literal(source.get('extract'))},",
            f"  {sql_literal(source.get('firstParagraph'))},",
            f"  {jsonb_literal(link_candidates)},",
            f"  {jsonb_literal(image_candidates)},",
            f"  {timestamptz_literal(source.get('fetchedAt'))},",
            f"  {sql_literal(hash_value)}",
            ") on conflict (topic_id, source_kind, source_hash) do update set",
            "  wikipedia_title = excluded.wikipedia_title,",
            "  wikipedia_page_id = excluded.wikipedia_page_id,",
            "  wikipedia_revision_id = excluded.wikipedia_revision_id,",
            "  raw_extract = excluded.raw_extract,",
            "  first_paragraph = excluded.first_paragraph,",
            "  link_candidates_json = excluded.link_candidates_json,",
            "  image_candidates_json = excluded.image_candidates_json,",
            "  fetched_at = excluded.fetched_at;",
        ]
    )
    return snapshot_id, sql


def generation_insert(topic_id: str, snapshot_id: str, card_data: dict[str, Any]) -> str:
    card = card_data["card"]
    quality = card_data.get("quality", {})
    generation_id = stable_uuid("llm_card_generation", topic_id, snapshot_id)
    return statement(
        [
            "insert into llm_card_generations (",
            "  id, topic_id, source_snapshot_id, provider, model, prompt_version,",
            "  generated_title, generated_pillar, generated_explanation, generated_hook_type,",
            "  generated_hook_text, related_candidates_json, confidence_notes_json,",
            "  grounding_status, quality_status, reviewer_notes",
            ") values (",
            f"  {uuid_literal(generation_id)},",
            f"  {sql_literal(topic_id)},",
            f"  {uuid_literal(snapshot_id)},",
            "  'local',",
            "  'deterministic-wikipedia-condenser',",
            "  'step-01-local-v1',",
            f"  {sql_literal(card['title'])},",
            f"  {sql_literal(card['pillar'])},",
            f"  {sql_literal(card['explanation'])},",
            f"  {sql_literal(card['hookType'])},",
            f"  {sql_literal(card['hook'])},",
            f"  {jsonb_literal(card.get('relatedCandidates', []))},",
            f"  {jsonb_literal(card.get('confidenceNotes', []))},",
            "  'passed',",
            f"  {sql_literal(quality.get('status', 'prototype_pass'))},",
            f"  {sql_literal('; '.join(quality.get('issues', [])) if quality.get('issues') else None)}",
            ") on conflict (id) do update set",
            "  generated_title = excluded.generated_title,",
            "  generated_pillar = excluded.generated_pillar,",
            "  generated_explanation = excluded.generated_explanation,",
            "  generated_hook_type = excluded.generated_hook_type,",
            "  generated_hook_text = excluded.generated_hook_text,",
            "  related_candidates_json = excluded.related_candidates_json,",
            "  confidence_notes_json = excluded.confidence_notes_json,",
            "  grounding_status = excluded.grounding_status,",
            "  quality_status = excluded.quality_status,",
            "  reviewer_notes = excluded.reviewer_notes;",
        ]
    )


def selected_image_statements(topic: dict[str, Any]) -> list[str]:
    topic_id = topic["id"]
    image = topic.get("image", {})
    selected = image.get("selected")
    strategy = image.get("strategy", "pillar_background")
    asset_id = stable_uuid("topic_asset", topic_id, strategy)
    output: list[str] = []

    if selected:
        candidate_id = stable_uuid("image_candidate", topic_id, selected.get("url"))
        attribution = selected.get("attribution") or selected.get("title") or selected.get("source")
        license_name = selected.get("license") or "unverified_wikimedia_license"
        output.append(
            statement(
                [
                    "insert into image_candidates (",
                    "  id, topic_id, source, source_title, url, thumbnail_url, width, height,",
                    "  license, attribution, media_type, quality_score, rejection_reason, selected",
                    ") values (",
                    f"  {uuid_literal(candidate_id)},",
                    f"  {sql_literal(topic_id)},",
                    f"  {sql_literal(selected.get('source', 'wikipedia'))},",
                    f"  {sql_literal(selected.get('title'))},",
                    f"  {sql_literal(selected.get('url'))},",
                    f"  {sql_literal(selected.get('thumbnailUrl'))},",
                    f"  {sql_literal(selected.get('width'))},",
                    f"  {sql_literal(selected.get('height'))},",
                    f"  {sql_literal(license_name)},",
                    f"  {sql_literal(attribution)},",
                    "  'image',",
                    f"  {sql_literal(selected.get('qualityScore'))},",
                    f"  {sql_literal('; '.join(selected.get('rejectionReasons', [])) if selected.get('rejectionReasons') else None)},",
                    "  true",
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
                    "  selected = true;",
                ]
            )
        )
        output.append(
            asset_insert(
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
            )
        )
    else:
        output.append(
            asset_insert(
                asset_id=asset_id,
                topic_id=topic_id,
                pillar=image.get("fallbackPillar") or topic.get("pillar"),
                image_candidate_id=None,
                asset_type="pillar_background",
                url=None,
                thumbnail_url=None,
                attribution="Wikis generated pillar background",
                license_name="internal",
                quality_score=None,
            )
        )

    output.append(
        statement(
            [
                "update topics",
                f"set image_asset_id = {uuid_literal(asset_id)}",
                f"where id = {sql_literal(topic_id)};",
            ]
        )
    )
    return output


def asset_insert(
    *,
    asset_id: str,
    topic_id: str | None,
    pillar: str | None,
    image_candidate_id: str | None,
    asset_type: str,
    url: str | None,
    thumbnail_url: str | None,
    attribution: str | None,
    license_name: str | None,
    quality_score: object,
) -> str:
    return statement(
        [
            "insert into topic_assets (",
            "  id, topic_id, pillar, image_candidate_id, asset_type, url, thumbnail_url,",
            "  attribution, license, quality_score, approved",
            ") values (",
            f"  {uuid_literal(asset_id)},",
            f"  {sql_literal(topic_id)},",
            f"  {sql_literal(pillar)},",
            f"  {uuid_literal(image_candidate_id)},",
            f"  {sql_literal(asset_type)},",
            f"  {sql_literal(url)},",
            f"  {sql_literal(thumbnail_url)},",
            f"  {sql_literal(attribution)},",
            f"  {sql_literal(license_name)},",
            f"  {sql_literal(quality_score)},",
            "  true",
            ") on conflict (id) do update set",
            "  topic_id = excluded.topic_id,",
            "  pillar = excluded.pillar,",
            "  image_candidate_id = excluded.image_candidate_id,",
            "  asset_type = excluded.asset_type,",
            "  url = excluded.url,",
            "  thumbnail_url = excluded.thumbnail_url,",
            "  attribution = excluded.attribution,",
            "  license = excluded.license,",
            "  quality_score = excluded.quality_score,",
            "  approved = excluded.approved;",
        ]
    )


def edge_insert(edge: dict[str, Any]) -> str:
    edge_id = stable_uuid("topic_edge", edge["id"])
    return statement(
        [
            "insert into topic_edges (",
            "  id, from_topic_id, to_topic_id, edge_type, strength, reason, status",
            ") values (",
            f"  {uuid_literal(edge_id)},",
            f"  {sql_literal(edge['from'])},",
            f"  {sql_literal(edge['to'])},",
            f"  {sql_literal(edge['type'])},",
            f"  {sql_literal(edge['strength'])},",
            f"  {sql_literal(edge['reason'])},",
            "  'approved'",
            ") on conflict (from_topic_id, to_topic_id, edge_type) do update set",
            "  strength = excluded.strength,",
            "  reason = excluded.reason,",
            "  status = excluded.status;",
        ]
    )


def candidate_edge_insert(candidate: dict[str, Any], from_topic_id: str | None, known_topics: set[str]) -> str:
    normalized = slugify(candidate["title"])
    candidate_id = stable_uuid("candidate_edge", candidate["source"], from_topic_id or "", normalized)
    to_topic_id = normalized if normalized in known_topics else None
    strength = min(1.0, max(0.1, candidate.get("priority", 1) / 100))
    return statement(
        [
            "insert into candidate_edges (",
            "  id, source, from_topic_id, from_title, to_topic_id, to_title, normalized_to_title,",
            "  extraction_method, candidate_strength, proposed_edge_type, status",
            ") values (",
            f"  {uuid_literal(candidate_id)},",
            f"  {sql_literal(candidate.get('source', 'wikipedia_lead_link'))},",
            f"  {sql_literal(from_topic_id)},",
            "  null,",
            f"  {sql_literal(to_topic_id)},",
            f"  {sql_literal(candidate['title'])},",
            f"  {sql_literal(normalized)},",
            "  'step_02_seed_graph_candidate_queue',",
            f"  {sql_literal(round(strength, 3))},",
            "  'neighbor',",
            "  'pending'",
            ") on conflict (source, coalesce(from_topic_id, ''), normalized_to_title, extraction_method) do update set",
            "  to_topic_id = excluded.to_topic_id,",
            "  to_title = excluded.to_title,",
            "  candidate_strength = excluded.candidate_strength,",
            "  proposed_edge_type = excluded.proposed_edge_type;",
        ]
    )


def generate_sql(graph_path: Path, cards_dir: Path) -> str:
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    cards = load_cards(cards_dir)
    known_topics = {topic["id"] for topic in graph["topics"]}
    statements: list[str] = [
        "-- Wikis Step 02 seed data for the production schema.",
        "-- Generated by scripts/seed_production_db.py.",
        "begin;",
    ]

    for topic in graph["topics"]:
        statements.append(topic_insert(topic))

    for topic in graph["topics"]:
        card_data = cards.get(topic["id"])
        if not card_data:
            continue
        snapshot_id, snapshot_sql = snapshot_insert(topic["id"], card_data)
        statements.append(snapshot_sql)
        statements.append(generation_insert(topic["id"], snapshot_id, card_data))
        statements.extend(selected_image_statements(topic))

    for edge in graph["edges"]:
        statements.append(edge_insert(edge))

    for candidate in graph.get("candidateQueue", []):
        seen_from = candidate.get("seenFrom") or [None]
        for from_topic_id in seen_from:
            statements.append(candidate_edge_insert(candidate, from_topic_id, known_topics))

    statements.append("commit;")
    return "\n".join(statements) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed production Postgres from Step 02 seed graph data.")
    parser.add_argument("--graph", type=Path, default=Path("data/graph/seed_graph.json"))
    parser.add_argument("--cards-dir", type=Path, default=Path("data/cards"))
    parser.add_argument("--out", type=Path, default=Path("migrations/002_seed_step02_graph.sql"))
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--execute", action="store_true", help="Apply generated SQL with psql.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sql = generate_sql(args.graph, args.cards_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(sql, encoding="utf-8")
    print(f"wrote {args.out}")

    if args.execute:
        if not args.database_url:
            print("--execute requires --database-url or DATABASE_URL", file=sys.stderr)
            return 2
        subprocess.run(
            ["psql", args.database_url, "-v", "ON_ERROR_STOP=1", "-f", str(args.out)],
            check=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
