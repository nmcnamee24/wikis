#!/usr/bin/env python3
"""Generate live Wikis cards for graph topic nodes.

By default this targets nodes that still have placeholder or missing card
content. Use --all to refresh every visible node in the live graph.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg

from backend_ingest import DEFAULT_LOCK_OWNER, DEFAULT_LOCK_TTL_MINUTES, card_output_sql, ingest_sql
from wiki_to_card import DEFAULT_OPENAI_MODEL, SourcePacket, build_card_output_from_packet, wiki_api


PLACEHOLDER_VERSION = "wikipedia-placeholder-v1"
PLACEHOLDER_EXPLANATION = "Card not generated yet, check back soon!"
LOCK_OWNER = "generate_node_cards"


@dataclass(frozen=True)
class NodeTarget:
    topic_id: str
    title: str
    wikipedia_title: str
    generation_status: str
    generation_version: str | None
    quality_status: str


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def validate_database_url(database_url: str | None) -> str:
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")
    if "YOUR-PASSWORD" in database_url or "[" in database_url or "]" in database_url:
        raise RuntimeError("DATABASE_URL still contains the Supabase dashboard password placeholder")
    if not database_url.startswith(("postgres://", "postgresql://")):
        raise RuntimeError("DATABASE_URL must be a Postgres connection string")
    return database_url


def connect_database(database_url: str) -> psycopg.Connection[Any]:
    return psycopg.connect(validate_database_url(database_url), prepare_threshold=None)


def load_targets(
    database_url: str,
    *,
    all_nodes: bool,
    include_failed: bool,
    limit: int | None,
) -> list[NodeTarget]:
    status_filter = "" if include_failed else "and generation_status <> 'failed'"
    if all_nodes:
        target_filter = "true"
    else:
        target_filter = """
          (
            generation_status in ('missing', 'provisional')
            or generation_version = 'wikipedia-placeholder-v1'
            or short_explanation = 'Card not generated yet, check back soon!'
            or hook_text = 'Card not generated yet, check back soon!'
          )
        """
    limit_sql = "limit %s" if limit is not None else ""
    sql = f"""
        select
          id,
          title,
          coalesce(canonical_wikipedia_title, title) as wikipedia_title,
          generation_status,
          generation_version,
          quality_status
        from topics
        where quality_status in ('approved', 'prototype_pass', 'needs_review', 'draft')
          {status_filter}
          and {target_filter}
        order by
          case when generation_version = 'wikipedia-placeholder-v1' then 0 else 1 end,
          id
        {limit_sql};
    """
    with connect_database(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, (limit,) if limit is not None else None)
            return [
                NodeTarget(
                    topic_id=row[0],
                    title=row[1],
                    wikipedia_title=row[2],
                    generation_status=row[3],
                    generation_version=row[4],
                    quality_status=row[5],
                )
                for row in cursor.fetchall()
            ]


def mark_generating(database_url: str, target: NodeTarget, lock_owner: str, lock_ttl_minutes: int) -> None:
    lock_key = f"node:{target.topic_id}"
    with connect_database(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                insert into generation_locks (
                  lock_key, target_kind, target_id, lock_owner, locked_until, generation_version
                ) values (
                  %s, 'node', %s, %s, now() + (%s::text || ' minutes')::interval, 'step-05-node-v1'
                )
                on conflict (lock_key) do update set
                  lock_owner = excluded.lock_owner,
                  locked_until = excluded.locked_until,
                  generation_version = excluded.generation_version
                where generation_locks.locked_until < now()
                   or generation_locks.lock_owner = excluded.lock_owner;
                """,
                (lock_key, target.topic_id, lock_owner, lock_ttl_minutes),
            )
            if cursor.rowcount == 0:
                raise RuntimeError(f"{target.topic_id} is locked by another generator")
            cursor.execute(
                """
                update topics
                set generation_status = 'generating',
                    generation_error = null
                where id = %s;
                """,
                (target.topic_id,),
            )
        connection.commit()


def mark_failed(database_url: str, target: NodeTarget, error: str) -> None:
    with connect_database(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                update topics
                set generation_status = 'failed',
                    generation_error = %s
                where id = %s;
                """,
                (error[:1000], target.topic_id),
            )
        connection.commit()


def mark_retryable(database_url: str, target: NodeTarget, error: str) -> None:
    with connect_database(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                update topics
                set generation_status = 'missing',
                    generation_error = %s
                where id = %s;
                """,
                (error[:1000], target.topic_id),
            )
        connection.commit()


def record_error(database_url: str, target: NodeTarget, error: str, *, execute: bool, mark_failed_on_error: bool) -> None:
    if not execute:
        return
    if mark_failed_on_error:
        mark_failed(database_url, target, error)
    else:
        mark_retryable(database_url, target, error)


def generate_target(
    database_url: str,
    target: NodeTarget,
    *,
    cards_out: Path | None,
    condenser: str,
    openai_model: str | None,
    execute: bool,
    lock_owner: str,
    lock_ttl_minutes: int,
    sql_out: Path | None,
    include_images: bool,
) -> str:
    if execute:
        mark_generating(database_url, target, lock_owner, lock_ttl_minutes)
    topic_id, sql = ingest_sql(
        target.wikipedia_title,
        "batch",
        cards_out,
        condenser,
        openai_model,
        lock_owner,
        lock_ttl_minutes,
        topic_id_override=target.topic_id,
        include_images=include_images,
    )
    if sql_out:
        sql_out.parent.mkdir(parents=True, exist_ok=True)
        with sql_out.open("a", encoding="utf-8") as handle:
            handle.write(sql)
            handle.write("\n")
    if execute:
        execute_sql_quietly(database_url, sql)
    return topic_id


def generate_target_from_packet(
    database_url: str,
    target: NodeTarget,
    packet: SourcePacket,
    *,
    cards_out: Path | None,
    condenser: str,
    openai_model: str | None,
    execute: bool,
    lock_owner: str,
    lock_ttl_minutes: int,
    sql_out: Path | None,
) -> str:
    if execute:
        mark_generating(database_url, target, lock_owner, lock_ttl_minutes)
    card_output = build_card_output_from_packet(packet, condenser=condenser, model=openai_model)
    topic_id, sql = card_output_sql(
        target.wikipedia_title,
        "batch",
        cards_out,
        card_output,
        lock_owner,
        lock_ttl_minutes,
        topic_id_override=target.topic_id,
    )
    if sql_out:
        sql_out.parent.mkdir(parents=True, exist_ok=True)
        with sql_out.open("a", encoding="utf-8") as handle:
            handle.write(sql)
            handle.write("\n")
    if execute:
        execute_sql_quietly(database_url, sql)
    return topic_id


def chunks(items: list[NodeTarget], size: int) -> list[list[NodeTarget]]:
    return [items[index:index + size] for index in range(0, len(items), size)]


def title_lookup_key(title: str) -> str:
    return title.replace("_", " ").strip().casefold()


def batch_fetch_source_packets(targets: list[NodeTarget]) -> dict[str, SourcePacket]:
    requested_titles = [target.wikipedia_title for target in targets]
    data = wiki_api(
        {
            "action": "query",
            "titles": "|".join(requested_titles),
            "redirects": 1,
            "prop": "extracts|info",
            "exintro": 1,
            "explaintext": 1,
            "inprop": "url",
        }
    )
    title_aliases = {title_lookup_key(title): title for title in requested_titles}
    for item in data.get("query", {}).get("normalized", []) or []:
        source = item.get("from")
        target = item.get("to")
        if source and target:
            title_aliases[title_lookup_key(source)] = target
    for item in data.get("query", {}).get("redirects", []) or []:
        source = item.get("from")
        target = item.get("to")
        if source and target:
            title_aliases[title_lookup_key(source)] = target

    pages_by_title = {
        title_lookup_key(page.get("title", "")): page
        for page in data.get("query", {}).get("pages", [])
        if not page.get("missing")
    }
    fetched_at = dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()
    packets: dict[str, SourcePacket] = {}
    for target in targets:
        normalized_title = title_aliases.get(title_lookup_key(target.wikipedia_title), target.wikipedia_title)
        page = pages_by_title.get(title_lookup_key(normalized_title))
        if not page:
            continue
        packets[target.topic_id] = SourcePacket(
            requested_title=target.wikipedia_title,
            normalized_title=page["title"],
            page_id=int(page["pageid"]),
            revision_id=page.get("lastrevid"),
            extract=str(page.get("extract", "")),
            lead_html="",
            image_candidates=[],
            fetched_at=fetched_at,
        )
    return packets


def execute_sql_quietly(database_url: str, sql: str) -> None:
    with connect_database(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate condensed Wikis cards for live graph nodes.")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--execute", action="store_true", help="Write generated cards to the live database.")
    parser.add_argument("--all", action="store_true", help="Refresh every visible node, not only placeholder/missing cards.")
    parser.add_argument("--include-failed", action="store_true", help="Include nodes currently marked failed.")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--cards-out", type=Path)
    parser.add_argument("--sql-out", type=Path)
    parser.add_argument("--condenser", choices=["local", "openai"], default="local")
    parser.add_argument("--openai-model", default=os.environ.get("WIKIS_OPENAI_MODEL", DEFAULT_OPENAI_MODEL))
    parser.add_argument("--include-images", action="store_true", help="Fetch Wikipedia page images instead of using pillar backgrounds.")
    parser.add_argument("--batch-size", type=int, default=50, help="Wikipedia titles per source fetch for local text-only generation.")
    parser.add_argument("--watch", action="store_true", help="Continuously poll for new placeholder/missing nodes and generate them.")
    parser.add_argument("--poll-interval", type=float, default=15.0, help="Seconds to wait between watch-mode polls when no targets are available.")
    parser.add_argument("--mark-failed-on-error", action="store_true", help="Mark failed nodes as failed instead of leaving them retryable.")
    parser.add_argument("--lock-owner", default=os.environ.get("WIKIS_INGEST_LOCK_OWNER", LOCK_OWNER))
    parser.add_argument("--lock-ttl-minutes", type=int, default=DEFAULT_LOCK_TTL_MINUTES)
    return parser.parse_args()


def process_targets(
    args: argparse.Namespace,
    database_url: str,
    targets: list[NodeTarget],
    *,
    truncate_sql_out: bool,
) -> dict[str, Any]:
    if truncate_sql_out and args.sql_out and args.sql_out.exists():
        args.sql_out.unlink()

    print(
        json.dumps(
            {
                "targetCount": len(targets),
                "mode": "all" if args.all else "placeholder_or_missing",
                "execute": args.execute,
                "condenser": args.condenser,
            },
            indent=2,
        )
    )
    if not args.execute and not args.sql_out and not args.cards_out:
        for index, target in enumerate(targets, start=1):
            print(f"{index}/{len(targets)} {target.topic_id}: {target.wikipedia_title}")
        summary = {"attempted": 0, "previewed": len(targets), "execute": False}
        print(json.dumps(summary, indent=2))
        return summary

    failures = 0
    completed = 0
    use_batch_fetch = args.condenser == "local" and not args.include_images and args.batch_size > 1

    if use_batch_fetch:
        target_chunks = chunks(targets, args.batch_size)
        for group_index, group in enumerate(target_chunks, start=1):
            try:
                packets = batch_fetch_source_packets(group)
            except Exception as exc:  # noqa: BLE001 - keep later chunks moving.
                completed += len(group)
                failures += len(group)
                print(f"ERROR chunk {group_index}: {exc}", file=sys.stderr)
                if args.execute and args.mark_failed_on_error:
                    for target in group:
                        mark_failed(database_url, target, str(exc))
                continue

            for target in group:
                completed += 1
                packet = packets.get(target.topic_id)
                if not packet:
                    failures += 1
                    error = "Wikipedia page not found in batch response"
                    print(f"ERROR {completed}/{len(targets)} {target.wikipedia_title}: {error}", file=sys.stderr)
                    record_error(
                        database_url,
                        target,
                        error,
                        execute=args.execute,
                        mark_failed_on_error=args.mark_failed_on_error,
                    )
                    continue
                try:
                    generated_id = generate_target_from_packet(
                        database_url,
                        target,
                        packet,
                        cards_out=args.cards_out,
                        condenser=args.condenser,
                        openai_model=args.openai_model,
                        execute=args.execute,
                        lock_owner=args.lock_owner or DEFAULT_LOCK_OWNER,
                        lock_ttl_minutes=args.lock_ttl_minutes,
                        sql_out=args.sql_out,
                    )
                    print(f"{completed}/{len(targets)} {target.wikipedia_title} -> {generated_id}")
                except Exception as exc:  # noqa: BLE001 - batch generator should keep moving.
                    failures += 1
                    print(f"ERROR {completed}/{len(targets)} {target.wikipedia_title}: {exc}", file=sys.stderr)
                    record_error(
                        database_url,
                        target,
                        str(exc),
                        execute=args.execute,
                        mark_failed_on_error=args.mark_failed_on_error,
                    )
            if group_index < len(target_chunks) and args.delay > 0:
                time.sleep(args.delay)
    else:
        for index, target in enumerate(targets, start=1):
            completed = index
            try:
                generated_id = generate_target(
                    database_url,
                    target,
                    cards_out=args.cards_out,
                    condenser=args.condenser,
                    openai_model=args.openai_model,
                    execute=args.execute,
                    lock_owner=args.lock_owner or DEFAULT_LOCK_OWNER,
                    lock_ttl_minutes=args.lock_ttl_minutes,
                    sql_out=args.sql_out,
                    include_images=args.include_images,
                )
                print(f"{index}/{len(targets)} {target.wikipedia_title} -> {generated_id}")
            except Exception as exc:  # noqa: BLE001 - batch generator should keep moving.
                failures += 1
                print(f"ERROR {index}/{len(targets)} {target.wikipedia_title}: {exc}", file=sys.stderr)
                record_error(
                    database_url,
                    target,
                    str(exc),
                    execute=args.execute,
                    mark_failed_on_error=args.mark_failed_on_error,
                )
            if index < len(targets) and args.delay > 0:
                time.sleep(args.delay)

    summary = {
        "attempted": completed,
        "succeeded": completed - failures,
        "failed": failures,
        "execute": args.execute,
    }
    print(json.dumps(summary, indent=2))
    return summary


def main() -> int:
    args = parse_args()
    load_dotenv(args.env_file)
    database_url = validate_database_url(args.database_url or os.environ.get("DATABASE_URL"))
    if args.watch and not args.execute:
        raise RuntimeError("--watch requires --execute so new nodes are hydrated live")
    if args.watch and args.all:
        raise RuntimeError("--watch cannot be combined with --all; watch mode only hydrates missing/new nodes")

    first_pass = True
    while True:
        targets = load_targets(
            database_url,
            all_nodes=args.all,
            include_failed=args.include_failed,
            limit=args.limit,
        )
        if targets:
            summary = process_targets(args, database_url, targets, truncate_sql_out=first_pass)
            first_pass = False
            if not args.watch:
                return 1 if summary.get("failed") else 0
            continue

        summary = process_targets(args, database_url, targets, truncate_sql_out=first_pass)
        first_pass = False
        if not args.watch:
            return 1 if summary.get("failed") else 0

        print(
            json.dumps(
                {
                    "watch": "idle",
                    "pollIntervalSeconds": args.poll_interval,
                    "checkedAt": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat(),
                },
                indent=2,
            )
        )
        time.sleep(args.poll_interval)


if __name__ == "__main__":
    raise SystemExit(main())
