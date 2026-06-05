#!/usr/bin/env python3
"""Run acceptance verification for Wikis implementation Steps 1-6."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib import request


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def run(command: list[str], label: str) -> None:
    print(f"== {label}")
    subprocess.run(command, check=True)


def psql_scalar(sql: str) -> str:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required for Supabase verification")
    result = subprocess.run(
        ["psql", database_url, "-v", "ON_ERROR_STOP=1", "-Atc", sql],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def verify_database() -> None:
    print("== Step 4/5 Supabase database")
    rls_missing = psql_scalar(
        """
        select count(*)
        from pg_class c
        join pg_namespace n on n.oid = c.relnamespace
        where n.nspname = 'public'
          and c.relkind = 'r'
          and c.relname in (
            'topics',
            'topic_source_snapshots',
            'llm_card_generations',
            'image_candidates',
            'topic_assets',
            'topic_edges',
            'candidate_edges',
            'app_users',
            'exploration_events',
            'saved_topics',
            'ingestion_jobs',
            'ingestion_review_events',
            'generation_locks'
          )
          and not c.relrowsecurity;
        """
    )
    print(f"rls_missing_tables: {rls_missing}")
    if rls_missing != "0":
        raise RuntimeError("one or more public tables are missing RLS")

    counts = psql_scalar(
        """
        select
          (select count(*) from topics),
          (select count(*) from topic_source_snapshots),
          (select count(*) from llm_card_generations),
          (select count(*) from topic_edges),
          (select count(*) from candidate_edges),
          (select count(*) from topics where generation_status = 'ready');
        """
    )
    values = [int(item) for item in counts.split("|")]
    labels = ["topics", "snapshots", "generations", "edges", "candidate_edges", "ready_topics"]
    print(dict(zip(labels, values)))
    if values[0] < 100 or values[1] < 100 or values[2] < 100 or values[3] < 700 or values[5] < 100:
        raise RuntimeError(f"database counts below acceptance thresholds: {counts}")

    ada = psql_scalar(
        "select quality_status || '|' || review_status || '|' || generation_status from topics where id = 'ada-lovelace';"
    )
    print(f"ada-lovelace: {ada}")
    if ada != "approved|approved|ready":
        raise RuntimeError("Ada Lovelace live ingestion approval is not ready")


def http_json(url: str, payload: dict | None = None) -> tuple[int, dict]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = request.Request(url, data=data, headers=headers, method="POST" if payload is not None else "GET")
    try:
        with request.urlopen(req, timeout=20) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"HTTP verification failed for {url}: {exc}") from exc


def verify_api(base_url: str) -> None:
    print("== Step 6 Railway API")
    status, root = http_json(f"{base_url.rstrip('/')}/")
    print(f"root: {status} {root.get('status')}")
    if status != 200 or root.get("status") != "ok":
        raise RuntimeError("root endpoint failed")

    status, health = http_json(f"{base_url.rstrip('/')}/health")
    print(f"health: {status} {health}")
    if status != 200 or health.get("status") != "ok":
        raise RuntimeError("health endpoint failed")

    status, down = http_json(
        f"{base_url.rstrip('/')}/v1/feed/next",
        {
            "currentTopicId": "black-hole",
            "gesture": "down",
            "exploredTopicIds": ["black-hole"],
            "frontierLimit": 2,
            "prefetchLimit": 3,
        },
    )
    print(f"black-hole/down: {status} {down.get('nextTopicId')} {down.get('reasonCode')}")
    if down.get("nextTopicId") != "event-horizon" or down.get("reasonCode") != "best_deeper_edge":
        raise RuntimeError("feed next down route failed")

    status, ada = http_json(
        f"{base_url.rstrip('/')}/v1/feed/next",
        {
            "currentTopicId": "ada-lovelace",
            "gesture": "right",
            "exploredTopicIds": ["ada-lovelace"],
            "frontierLimit": 2,
            "prefetchLimit": 3,
        },
    )
    print(f"ada/right: {status} {ada.get('nextTopicId')} background={len(ada.get('backgroundIngestionTopics', []))}")
    if len(ada.get("backgroundIngestionTopics", [])) > 2:
        raise RuntimeError("frontier cap failed")

    status, event = http_json(
        f"{base_url.rstrip('/')}/v1/events",
        {
            "sessionId": "verify-steps-1-6",
            "anonymousSessionId": "verify-steps-1-6",
            "fromTopicId": "black-hole",
            "toTopicId": "event-horizon",
            "gesture": "down",
            "reasonCode": "best_deeper_edge",
            "dwellMs": 1234,
        },
    )
    print(f"event: {status} {event.get('status')}")
    if status != 200 or event.get("status") != "recorded":
        raise RuntimeError("event recording failed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify Wikis Steps 1-6.")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--api-url", default=os.environ.get("WIKIS_API_URL", "https://wikis-api-production.up.railway.app"))
    parser.add_argument("--skip-live", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(args.env_file)
    run(["python3", "-m", "py_compile", "scripts/wiki_to_card.py", "scripts/build_seed_graph.py", "scripts/validate_seed_graph.py", "scripts/validate_cards.py", "scripts/backend_ingest.py", "scripts/feed_next.py", "scripts/apply_supabase_db.py"], "Python compile")
    run(["python3", "scripts/validate_cards.py", "--min-cards", "100"], "Step 1 card validation")
    run(["python3", "scripts/validate_seed_graph.py", "data/graph/seed_graph.json"], "Step 2 graph validation")
    run(["swift", "build", "--product", "WikisPrototype"], "Step 3 core build")
    run(["swift", "run", "WikisCoreSmokeTests", "data/graph/seed_graph.json"], "Step 3/6 core smoke")
    if not args.skip_live:
        verify_database()
        verify_api(args.api_url)
    print("Steps 1-6 verification passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
