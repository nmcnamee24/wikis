#!/usr/bin/env python3
"""Procedurally expand Wikis topics from Wikipedia lead links.

This is a thin orchestration layer over ``backend_ingest.py``:

seed topic -> generate card -> take first N Wikipedia links -> enqueue/generate
children -> repeat until max depth or topic cap.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend_ingest import (
    DEFAULT_LOCK_OWNER,
    DEFAULT_LOCK_TTL_MINUTES,
    DEFAULT_OPENAI_MODEL,
    NODE_GENERATION_VERSION,
    ingest_sql,
    job_statement,
    statement,
    write_or_execute,
)
from wiki_to_card import slugify


@dataclass(frozen=True)
class FrontierItem:
    title: str
    depth: int
    parent: str | None = None


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


def load_generated_card(cards_out: Path, topic_id: str) -> dict[str, Any]:
    path = cards_out / f"{topic_id}.json"
    if not path.exists():
        raise RuntimeError(f"generated card was not written: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def first_links(card_output: dict[str, Any], limit: int) -> list[str]:
    links = card_output.get("mapping", {}).get("leadOrFallbackLinks", [])
    output: list[str] = []
    seen: set[str] = set()
    for link in links:
        title = str(link.get("title", "")).strip()
        slug = slugify(title)
        if not title or slug in seen:
            continue
        seen.add(slug)
        output.append(title)
        if len(output) >= limit:
            break
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a bounded procedural Wikis expansion from one Wikipedia topic."
    )
    parser.add_argument("seed_title", help="Starting Wikipedia page title, for example 'Black hole'.")
    parser.add_argument("--links-per-topic", type=int, default=5, help="Number of first links to expand from each generated topic.")
    parser.add_argument("--max-depth", type=int, default=1, help="Expansion distance from the seed. 0 generates only the seed.")
    parser.add_argument("--max-topics", type=int, default=25, help="Hard cap on generated topics, including the seed.")
    parser.add_argument("--cards-out", type=Path, default=Path("data/cards"))
    parser.add_argument("--sql-out", type=Path, help="Write combined ingestion SQL to this path.")
    parser.add_argument("--manifest-out", type=Path, help="Write expansion manifest JSON to this path.")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--execute", action="store_true", help="Apply the generated SQL to Postgres/Supabase with psql.")
    parser.add_argument("--source", choices=["manual", "batch", "candidate_queue", "background_expansion"], default="background_expansion")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds to wait between Wikipedia/OpenAI calls.")
    parser.add_argument("--condenser", choices=["local", "openai"], default="openai")
    parser.add_argument("--openai-model", default=os.environ.get("WIKIS_OPENAI_MODEL", DEFAULT_OPENAI_MODEL))
    parser.add_argument("--lock-owner", default=os.environ.get("WIKIS_INGEST_LOCK_OWNER", DEFAULT_LOCK_OWNER))
    parser.add_argument("--lock-ttl-minutes", type=int, default=DEFAULT_LOCK_TTL_MINUTES)
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.links_per_topic < 0:
        raise ValueError("--links-per-topic must be >= 0")
    if args.max_depth < 0:
        raise ValueError("--max-depth must be >= 0")
    if args.max_topics < 1:
        raise ValueError("--max-topics must be >= 1")
    if args.condenser == "openai" and not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required for --condenser openai. Use --condenser local for a no-key test run.")


def main() -> int:
    load_dotenv()
    args = parse_args()
    try:
        validate_args(args)
    except Exception as exc:  # noqa: BLE001 - CLI should print concise setup errors.
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    frontier: deque[FrontierItem] = deque([FrontierItem(args.seed_title, 0)])
    seen_slugs: set[str] = set()
    generated: list[dict[str, Any]] = []
    sql_blocks: list[str] = []
    failures = 0

    while frontier and len(generated) < args.max_topics:
        item = frontier.popleft()
        requested_slug = slugify(item.title)
        if requested_slug in seen_slugs:
            continue
        seen_slugs.add(requested_slug)

        try:
            topic_id, sql = ingest_sql(
                item.title,
                args.source,
                args.cards_out,
                args.condenser,
                args.openai_model,
                args.lock_owner,
                args.lock_ttl_minutes,
            )
            sql_blocks.append(sql)
            card_output = load_generated_card(args.cards_out, topic_id)
            child_titles = first_links(card_output, args.links_per_topic)
            generated.append(
                {
                    "title": card_output["source"]["wikipediaTitle"],
                    "topic_id": topic_id,
                    "depth": item.depth,
                    "parent": item.parent,
                    "candidate_links": child_titles,
                    "quality_status": card_output["quality"]["status"],
                    "quality_issues": card_output["quality"].get("issues", []),
                    "generation": card_output.get("generation", {}),
                }
            )
            print(f"{item.title} -> {topic_id} depth={item.depth} links={len(child_titles)}")

            if item.depth < args.max_depth:
                for child_title in child_titles:
                    if len(generated) + len(frontier) >= args.max_topics:
                        break
                    if slugify(child_title) not in seen_slugs:
                        frontier.append(FrontierItem(child_title, item.depth + 1, topic_id))
        except Exception as exc:  # noqa: BLE001 - keep batch expansion observable.
            failures += 1
            sql_blocks.append(
                statement(
                    [
                        "begin;",
                        job_statement(
                            item.title,
                            args.source,
                            "failed",
                            error=str(exc),
                            generation_version=NODE_GENERATION_VERSION,
                            frontier_depth=item.depth,
                            frontier_limit=args.links_per_topic,
                        ),
                        "commit;",
                    ]
                )
            )
            print(f"ERROR: {item.title}: {exc}", file=sys.stderr)

        if frontier and args.delay > 0:
            time.sleep(args.delay)

    manifest = {
        "seed_title": args.seed_title,
        "links_per_topic": args.links_per_topic,
        "max_depth": args.max_depth,
        "max_topics": args.max_topics,
        "generated_count": len(generated),
        "failure_count": failures,
        "topics": generated,
    }
    if args.manifest_out:
        args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
        args.manifest_out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {args.manifest_out}")

    write_or_execute("\n".join(sql_blocks), args.sql_out, args.database_url, args.execute)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
