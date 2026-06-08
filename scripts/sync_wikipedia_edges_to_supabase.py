#!/usr/bin/env python3
"""Reset Supabase graph edges from Wikipedia first-paragraph links.

Depth is intentionally one: existing Supabase topics are roots, and missing
linked pages are staged as candidates for the existing condensation pipeline.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_wikipedia_expansion_graph import classify_edge, fetch_lead_links, slugify
from seed_production_db import sql_literal, stable_uuid, statement, uuid_literal


EDGE_SOURCE = "wikipedia_first_paragraph_link"
EXTRACTION_METHOD = "wikipedia_parse_section_0"
NODE_GENERATION_VERSION = "step-05-node-v1"
EDGE_GENERATION_VERSION = "wikipedia-edge-reset-v1"


@dataclass(frozen=True)
class TopicRoot:
    id: str
    title: str
    fetch_title: str
    page_id: int | None


@dataclass(frozen=True)
class LinkRecord:
    from_topic_id: str
    from_title: str
    source_page_id: int | None
    to_title: str
    to_topic_id: str | None
    normalized_to_title: str
    label: str
    edge_type: str
    rank: int
    strength: float


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def validate_database_url(database_url: str | None) -> str:
    if not database_url:
        raise RuntimeError("DATABASE_URL is required to read existing Supabase topics")
    if "YOUR-PASSWORD" in database_url or "[" in database_url or "]" in database_url:
        raise RuntimeError("DATABASE_URL still contains the Supabase dashboard password placeholder")
    if not database_url.startswith(("postgresql://", "postgres://")):
        raise RuntimeError("DATABASE_URL must be a Postgres connection string")
    return database_url


def fetch_topic_rows(database_url: str, max_topics: int | None = None) -> list[dict[str, Any]]:
    sql = """
select
  t.id,
  t.title,
  t.canonical_wikipedia_title,
  s.wikipedia_title as snapshot_wikipedia_title,
  s.wikipedia_page_id
from topics t
left join lateral (
  select wikipedia_title, wikipedia_page_id
  from topic_source_snapshots
  where topic_id = t.id
  order by created_at desc
  limit 1
) s on true
where t.quality_status in ('approved', 'prototype_pass', 'needs_review')
  and t.generation_status <> 'failed'
order by t.title
"""
    if max_topics is not None:
        sql += f"limit {int(max_topics)}\n"
    sql += ";"

    try:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(database_url, row_factory=dict_row) as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql)
                return [dict(row) for row in cursor.fetchall()]
    except ModuleNotFoundError:
        result = subprocess.run(
            ["psql", database_url, "-v", "ON_ERROR_STOP=1", "-Atc", f"copy ({sql.rstrip(';')}) to stdout with csv header"],
            check=True,
            capture_output=True,
            text=True,
        )
        import csv
        from io import StringIO

        return list(csv.DictReader(StringIO(result.stdout)))


def topic_roots(rows: list[dict[str, Any]]) -> list[TopicRoot]:
    roots: list[TopicRoot] = []
    for row in rows:
        fetch_title = (
            row.get("canonical_wikipedia_title")
            or row.get("snapshot_wikipedia_title")
            or row.get("title")
            or row["id"]
        )
        page_id = row.get("wikipedia_page_id")
        roots.append(
            TopicRoot(
                id=str(row["id"]),
                title=str(row.get("title") or fetch_title),
                fetch_title=str(fetch_title),
                page_id=int(page_id) if page_id not in {None, ""} else None,
            )
        )
    return roots


def build_topic_aliases(rows: list[dict[str, Any]]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for row in rows:
        topic_id = str(row["id"])
        candidates = [
            topic_id,
            row.get("title"),
            row.get("canonical_wikipedia_title"),
            row.get("snapshot_wikipedia_title"),
        ]
        for value in candidates:
            if not value:
                continue
            text = str(value).strip()
            aliases[text.lower()] = topic_id
            aliases[slugify(text)] = topic_id
    return aliases


def strength_for_rank(index: int) -> float:
    return round(max(0.2, 0.86 - (index * 0.04)), 3)


def collect_links(roots: list[TopicRoot], aliases: dict[str, str], links_per_topic: int, delay: float) -> tuple[list[LinkRecord], list[dict[str, str]]]:
    records: list[LinkRecord] = []
    failures: list[dict[str, str]] = []

    for root_index, root in enumerate(roots):
        try:
            canonical_title, page_id, links = fetch_lead_links(root.fetch_title, links_per_topic)
            sibling_count = len(links)
            print(f"{root.title} -> {canonical_title} links={sibling_count}", flush=True)
            seen_targets: set[tuple[str, str]] = set()
            for index, link in enumerate(links):
                to_title = str(link["title"]).strip()
                normalized = slugify(to_title)
                to_topic_id = aliases.get(to_title.lower()) or aliases.get(normalized)
                if to_topic_id == root.id:
                    continue
                edge_type = classify_edge(index, sibling_count)
                dedupe_key = (to_topic_id or normalized, edge_type)
                if dedupe_key in seen_targets:
                    continue
                seen_targets.add(dedupe_key)
                records.append(
                    LinkRecord(
                        from_topic_id=root.id,
                        from_title=canonical_title,
                        source_page_id=page_id or root.page_id,
                        to_title=to_title,
                        to_topic_id=to_topic_id,
                        normalized_to_title=normalized,
                        label=str(link.get("label") or to_title),
                        edge_type=edge_type,
                        rank=index + 1,
                        strength=strength_for_rank(index),
                    )
                )
        except Exception as exc:  # noqa: BLE001 - one bad Wikipedia page should not stop the reset.
            failures.append({"topic_id": root.id, "title": root.fetch_title, "error": str(exc)})
            print(f"ERROR: {root.fetch_title}: {exc}", file=sys.stderr, flush=True)

        if root_index < len(roots) - 1 and delay > 0:
            time.sleep(delay)

    return records, failures


def reset_statements(delete_existing_edges: bool) -> list[str]:
    statements = [
        "-- Remove stale non-Wikipedia edge sources even when a full reset is disabled.",
        f"delete from topic_edges where reason <> {sql_literal(EDGE_SOURCE)};",
        f"delete from candidate_edges where source <> {sql_literal(EDGE_SOURCE)};",
    ]
    if delete_existing_edges:
        statements.extend(
            [
                "-- Destructive edge reset requested by --delete-existing-edges.",
                "delete from topic_edges;",
                "delete from candidate_edges;",
                "delete from ingestion_jobs",
                "where source = 'background_expansion'",
                "  and status in ('queued', 'retryable')",
                "  and topic_id is null;",
            ]
        )
    return statements


def topic_edge_statement(record: LinkRecord) -> str:
    assert record.to_topic_id is not None
    edge_id = stable_uuid(
        "topic_edge",
        EDGE_SOURCE,
        record.from_topic_id,
        record.to_topic_id,
        record.edge_type,
    )
    generation_hash = stable_uuid("edge_hash", EDGE_SOURCE, record.from_topic_id, record.to_topic_id, record.rank)
    evidence = json.dumps(
        {
            "fromTitle": record.from_title,
            "toTitle": record.to_title,
            "label": record.label,
            "rank": record.rank,
            "source": EDGE_SOURCE,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return statement(
        [
            "insert into topic_edges (",
            "  id, from_topic_id, to_topic_id, edge_type, strength, reason, status,",
            "  rank, confidence, source_evidence, generation_status, generation_version, generation_hash",
            ") values (",
            f"  {uuid_literal(edge_id)},",
            f"  {sql_literal(record.from_topic_id)},",
            f"  {sql_literal(record.to_topic_id)},",
            f"  {sql_literal(record.edge_type)},",
            f"  {sql_literal(record.strength)},",
            f"  {sql_literal(EDGE_SOURCE)},",
            "  'approved',",
            f"  {sql_literal(record.rank)},",
            f"  {sql_literal(record.strength)},",
            f"  {sql_literal(evidence)},",
            "  'ready',",
            f"  {sql_literal(EDGE_GENERATION_VERSION)},",
            f"  {sql_literal(generation_hash)}",
            ") on conflict (from_topic_id, to_topic_id, edge_type) do update set",
            "  strength = excluded.strength,",
            "  reason = excluded.reason,",
            "  status = excluded.status,",
            "  rank = excluded.rank,",
            "  confidence = excluded.confidence,",
            "  source_evidence = excluded.source_evidence,",
            "  generation_status = excluded.generation_status,",
            "  generation_version = excluded.generation_version,",
            "  generation_hash = excluded.generation_hash;",
        ]
    )


def candidate_edge_statement(record: LinkRecord) -> str:
    candidate_id = stable_uuid(
        "candidate_edge",
        EDGE_SOURCE,
        record.from_topic_id,
        record.normalized_to_title,
        EXTRACTION_METHOD,
    )
    return statement(
        [
            "insert into candidate_edges (",
            "  id, source, source_page_id, from_topic_id, from_title, to_topic_id, to_title,",
            "  normalized_to_title, raw_position, extraction_method, candidate_strength,",
            "  proposed_edge_type, status",
            ") values (",
            f"  {uuid_literal(candidate_id)},",
            f"  {sql_literal(EDGE_SOURCE)},",
            f"  {sql_literal(record.source_page_id)},",
            f"  {sql_literal(record.from_topic_id)},",
            f"  {sql_literal(record.from_title)},",
            "  null,",
            f"  {sql_literal(record.to_title)},",
            f"  {sql_literal(record.normalized_to_title)},",
            f"  {sql_literal(record.rank)},",
            f"  {sql_literal(EXTRACTION_METHOD)},",
            f"  {sql_literal(record.strength)},",
            f"  {sql_literal(record.edge_type)},",
            "  'pending'",
            ") on conflict (source, (coalesce(from_topic_id, ''::text)), normalized_to_title, extraction_method) do update set",
            "  source_page_id = excluded.source_page_id,",
            "  from_title = excluded.from_title,",
            "  to_title = excluded.to_title,",
            "  raw_position = excluded.raw_position,",
            "  candidate_strength = excluded.candidate_strength,",
            "  proposed_edge_type = excluded.proposed_edge_type,",
            "  status = 'pending';",
        ]
    )


def job_statement(title: str, normalized: str, priority: int) -> str:
    generation_hash = stable_uuid("node_hash", EDGE_SOURCE, normalized)
    return statement(
        [
            "insert into ingestion_jobs (",
            "  requested_title, normalized_title, source, priority, status, attempts,",
            "  job_kind, frontier_depth, frontier_limit, generation_version, generation_hash",
            ") values (",
            f"  {sql_literal(title)},",
            f"  {sql_literal(normalized)},",
            "  'background_expansion',",
            f"  {sql_literal(priority)},",
            "  'queued',",
            "  0,",
            "  'node',",
            "  1,",
            "  0,",
            f"  {sql_literal(NODE_GENERATION_VERSION)},",
            f"  {sql_literal(generation_hash)}",
            ") on conflict (requested_title, source) do update set",
            "  normalized_title = excluded.normalized_title,",
            "  priority = greatest(ingestion_jobs.priority, excluded.priority),",
            "  status = 'queued',",
            "  job_kind = excluded.job_kind,",
            "  frontier_depth = excluded.frontier_depth,",
            "  frontier_limit = excluded.frontier_limit,",
            "  generation_version = excluded.generation_version,",
            "  generation_hash = excluded.generation_hash",
            "where ingestion_jobs.status not in ('running', 'succeeded');",
        ]
    )


def generate_sql(records: list[LinkRecord], delete_existing_edges: bool) -> tuple[str, dict[str, int]]:
    topic_records = [record for record in records if record.to_topic_id]
    candidate_records = [record for record in records if not record.to_topic_id]

    best_missing: dict[str, tuple[str, int]] = {}
    for record in candidate_records:
        priority = int(record.strength * 1000)
        existing = best_missing.get(record.normalized_to_title)
        if existing is None or priority > existing[1]:
            best_missing[record.normalized_to_title] = (record.to_title, priority)

    statements: list[str] = [
        "-- Wikis Wikipedia edge reset.",
        "-- Generated by scripts/sync_wikipedia_edges_to_supabase.py.",
        "begin;",
        *reset_statements(delete_existing_edges),
    ]
    statements.extend(topic_edge_statement(record) for record in topic_records)
    statements.extend(candidate_edge_statement(record) for record in candidate_records)
    statements.extend(
        job_statement(title, normalized, priority)
        for normalized, (title, priority) in sorted(best_missing.items())
    )
    statements.extend(
        [
            "-- Enforce the product invariant: every stored edge is one of the first six Wikipedia links.",
            f"delete from topic_edges where reason <> {sql_literal(EDGE_SOURCE)} or rank is null or rank > 6;",
            f"delete from candidate_edges where source <> {sql_literal(EDGE_SOURCE)} or raw_position is null or raw_position > 6;",
            "do $$",
            "declare",
            "  invalid_topic_edges integer;",
            "  invalid_candidate_edges integer;",
            "begin",
            f"  select count(*) into invalid_topic_edges from topic_edges where reason <> {sql_literal(EDGE_SOURCE)} or rank is null or rank > 6;",
            f"  select count(*) into invalid_candidate_edges from candidate_edges where source <> {sql_literal(EDGE_SOURCE)} or raw_position is null or raw_position > 6;",
            "  if invalid_topic_edges > 0 or invalid_candidate_edges > 0 then",
            "    raise exception 'Wikipedia edge invariant failed: topic_edges=%, candidate_edges=%', invalid_topic_edges, invalid_candidate_edges;",
            "  end if;",
            "end $$;",
        ]
    )
    statements.append("commit;")

    stats = {
        "topic_edges": len(topic_records),
        "candidate_edges": len(candidate_records),
        "queued_jobs": len(best_missing),
    }
    return "\n".join(statements) + "\n", stats


def execute_sql(database_url: str, sql: str) -> None:
    try:
        import psycopg

        with psycopg.connect(database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql)
            connection.commit()
        return
    except ModuleNotFoundError:
        subprocess.run(
            ["psql", database_url, "-v", "ON_ERROR_STOP=1"],
            input=sql,
            text=True,
            check=True,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reset Supabase graph edges from Wikipedia lead links.")
    parser.add_argument("--links-per-topic", type=int, default=6)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--sql-out", type=Path, help="Write the generated SQL transaction without applying it.")
    parser.add_argument("--execute", action="store_true", help="Apply the destructive edge reset to Supabase.")
    parser.add_argument("--delete-existing-edges", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--max-topics", type=int, help="Optional smoke-test cap for topic roots.")
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.links_per_topic < 1:
        raise ValueError("--links-per-topic must be >= 1")
    if args.delay < 0:
        raise ValueError("--delay must be >= 0")
    if args.max_topics is not None and args.max_topics < 1:
        raise ValueError("--max-topics must be >= 1")


def main() -> int:
    args = parse_args()
    load_dotenv(args.env_file)
    try:
        validate_args(args)
        database_url = validate_database_url(args.database_url or os.environ.get("DATABASE_URL"))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    rows = fetch_topic_rows(database_url, args.max_topics)
    roots = topic_roots(rows)
    aliases = build_topic_aliases(rows)
    records, failures = collect_links(roots, aliases, args.links_per_topic, args.delay)
    sql, sql_stats = generate_sql(records, args.delete_existing_edges)

    if args.sql_out:
        args.sql_out.parent.mkdir(parents=True, exist_ok=True)
        args.sql_out.write_text(sql, encoding="utf-8")
        print(f"wrote {args.sql_out}")
    if args.execute:
        execute_sql(database_url, sql)
        print("applied Wikipedia edge reset to Supabase")
    elif not args.sql_out:
        print("dry run complete; pass --sql-out to write SQL or --execute to apply it")

    summary = {
        "topics_scanned": len(roots),
        "links_fetched": len(records),
        **sql_stats,
        "failures": len(failures),
    }
    print(json.dumps(summary, indent=2))
    if failures:
        print(json.dumps({"failures": failures[:20]}, indent=2), file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
