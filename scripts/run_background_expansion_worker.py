#!/usr/bin/env python3
"""Claim queued Wikipedia expansion jobs and generate topic cards.

This worker is intentionally bounded by --limit so it can run from cron, a
Railway worker service, or a local terminal without trying to crawl Wikipedia
unbounded in one process.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend_ingest import (  # noqa: E402
    DEFAULT_LOCK_OWNER,
    DEFAULT_LOCK_TTL_MINUTES,
    DEFAULT_OPENAI_MODEL,
    NODE_GENERATION_VERSION,
    ingest_sql,
    job_statement,
    statement,
)


def load_dotenv(path: Path) -> None:
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
        raise RuntimeError("DATABASE_URL is required")
    if "YOUR-PASSWORD" in database_url or "[" in database_url or "]" in database_url:
        raise RuntimeError("DATABASE_URL still contains the Supabase dashboard password placeholder")
    return database_url


def claim_jobs(database_url: str, limit: int, lock_owner: str, ttl_minutes: int) -> list[str]:
    import psycopg

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                with picked as (
                  select id
                  from ingestion_jobs
                  where source = 'background_expansion'
                    and job_kind in ('node', 'frontier')
                    and status in ('queued', 'retryable')
                    and (locked_until is null or locked_until < now())
                  order by priority desc nulls last, created_at
                  limit %s
                  for update skip locked
                )
                update ingestion_jobs job
                set status = 'running',
                    attempts = job.attempts + 1,
                    started_at = now(),
                    finished_at = null,
                    lock_owner = %s,
                    locked_until = now() + (%s::text || ' minutes')::interval,
                    last_error = null
                from picked
                where job.id = picked.id
                returning job.requested_title;
                """,
                (limit, lock_owner, ttl_minutes),
            )
            titles = [row[0] for row in cursor.fetchall()]
        connection.commit()
    return titles


def peek_jobs(database_url: str, limit: int) -> list[str]:
    import psycopg

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select requested_title
                from ingestion_jobs
                where source = 'background_expansion'
                  and job_kind in ('node', 'frontier')
                  and status in ('queued', 'retryable')
                  and (locked_until is null or locked_until < now())
                order by priority desc nulls last, created_at
                limit %s;
                """,
                (limit,),
            )
            return [row[0] for row in cursor.fetchall()]


def execute_sql(database_url: str, sql: str) -> None:
    import psycopg

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql)
        connection.commit()


def fail_job_sql(title: str, error: str) -> str:
    return statement(
        [
            "begin;",
            job_statement(
                title,
                "background_expansion",
                "failed",
                error=error,
                generation_version=NODE_GENERATION_VERSION,
                frontier_depth=1,
                frontier_limit=0,
            ),
            "commit;",
        ]
    )


def process_titles(args: argparse.Namespace, database_url: str, titles: list[str]) -> dict[str, Any]:
    stats = {"claimed": len(titles), "succeeded": 0, "failed": 0}
    for index, title in enumerate(titles):
        try:
            _, sql = ingest_sql(
                title,
                "background_expansion",
                args.cards_out,
                args.condenser,
                args.openai_model,
                args.lock_owner,
                args.lock_ttl_minutes,
            )
            if not args.dry_run:
                execute_sql(database_url, sql)
            stats["succeeded"] += 1
            print(f"{title} -> succeeded", flush=True)
        except Exception as exc:  # noqa: BLE001 - keep the batch moving and record failures.
            if not args.dry_run:
                execute_sql(database_url, fail_job_sql(title, str(exc)))
            stats["failed"] += 1
            print(f"ERROR: {title}: {exc}", file=sys.stderr, flush=True)
        if index < len(titles) - 1 and args.delay > 0:
            time.sleep(args.delay)
    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run queued Wikis background expansion jobs.")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--cards-out", type=Path, default=Path("data/cards"))
    parser.add_argument("--condenser", choices=["local", "openai"], default="openai")
    parser.add_argument("--openai-model", default=os.environ.get("WIKIS_OPENAI_MODEL", DEFAULT_OPENAI_MODEL))
    parser.add_argument("--lock-owner", default=os.environ.get("WIKIS_INGEST_LOCK_OWNER", DEFAULT_LOCK_OWNER))
    parser.add_argument("--lock-ttl-minutes", type=int, default=DEFAULT_LOCK_TTL_MINUTES)
    parser.add_argument("--dry-run", action="store_true", help="Peek and generate without claiming jobs or writing SQL.")
    parser.add_argument("--loop", action="store_true", help="Continue polling until stopped.")
    parser.add_argument("--sleep-seconds", type=float, default=15)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(args.env_file)
    try:
        if args.limit < 1:
            raise ValueError("--limit must be >= 1")
        if args.delay < 0 or args.sleep_seconds < 0:
            raise ValueError("--delay and --sleep-seconds must be >= 0")
        database_url = validate_database_url(args.database_url or os.environ.get("DATABASE_URL"))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    total = {"claimed": 0, "succeeded": 0, "failed": 0}
    while True:
        titles = (
            peek_jobs(database_url, args.limit)
            if args.dry_run
            else claim_jobs(database_url, args.limit, args.lock_owner, args.lock_ttl_minutes)
        )
        if not titles:
            print("no queued background expansion jobs")
            break
        stats = process_titles(args, database_url, titles)
        for key, value in stats.items():
            total[key] += value
        if not args.loop:
            break
        time.sleep(args.sleep_seconds)

    print(total)
    return 1 if total["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
