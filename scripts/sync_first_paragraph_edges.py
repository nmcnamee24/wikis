#!/usr/bin/env python3
"""Create basic Wikis edges from first-paragraph Wikipedia links.

This mirrors the reference Wikipedia Map behavior: expand each existing topic by
fetching the Wikipedia lead section, reading the first non-empty paragraph, and
connecting the topic to every Wikipedia article linked there.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import psycopg

import sql_helpers as seed_sql
from wiki_to_card import slugify


API_URL = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "WikisFirstParagraphEdges/0.1 (local development)"
GENERATION_VERSION = "wikipedia-first-paragraph-links-v1"
EDGE_REASON = "wikipedia_first_paragraph_link"
PLACEHOLDER_EXPLANATION = "Placeholder text for this Wikipedia topic. Full Wikis writing has not been generated yet."
PLACEHOLDER_HOOK = "This topic was added from a first-paragraph Wikipedia link."


@dataclass(frozen=True)
class TopicSeed:
    id: str
    title: str
    wikipedia_title: str


@dataclass(frozen=True)
class LinkTarget:
    title: str
    topic_id: str
    rank: int


class FirstParagraphLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_paragraph = False
        self.paragraph_depth = 0
        self.paragraph_links: list[str] = []
        self.paragraph_text: list[str] = []
        self.first_links: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag == "p" and self.first_links is None and not self.in_paragraph:
            classes = set((attr.get("class") or "").split())
            if "mw-empty-elt" in classes:
                return
            self.in_paragraph = True
            self.paragraph_depth = 1
            self.paragraph_links = []
            self.paragraph_text = []
            return

        if not self.in_paragraph:
            return

        self.paragraph_depth += 1
        if tag == "a":
            href = attr.get("href")
            if href:
                self.paragraph_links.append(href)

    def handle_endtag(self, tag: str) -> None:
        if not self.in_paragraph:
            return
        if tag != "p":
            self.paragraph_depth = max(1, self.paragraph_depth - 1)
            return
        if clean_text(" ".join(self.paragraph_text)):
            self.first_links = list(self.paragraph_links)
        self.in_paragraph = False
        self.paragraph_depth = 0

    def handle_data(self, data: str) -> None:
        if self.in_paragraph:
            self.paragraph_text.append(data)


def clean_text(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def validate_database_url(database_url: str) -> str:
    if "YOUR-PASSWORD" in database_url or "[" in database_url or "]" in database_url:
        raise RuntimeError("DATABASE_URL still contains the Supabase dashboard password placeholder")
    return database_url


def wiki_api(params: dict[str, Any], *, retries: int = 5) -> dict[str, Any]:
    query = {"format": "json", "formatversion": 2, **params}
    url = f"{API_URL}?{urllib.parse.urlencode(query, doseq=True)}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code == 429:
                retry_after = exc.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else min(45.0, 6.0 * (attempt + 1))
                time.sleep(delay)
                continue
            time.sleep(min(8.0, 0.75 * (2**attempt)))
        except Exception as exc:  # noqa: BLE001 - retry and surface the source title.
            last_error = exc
            time.sleep(min(8.0, 0.75 * (2**attempt)))
    raise RuntimeError(f"Wikipedia API request failed: {last_error}") from last_error


def title_from_wiki_href(href: str) -> str | None:
    if not href.startswith("/wiki/"):
        return None
    title = urllib.parse.unquote(href.removeprefix("/wiki/")).split("#", 1)[0]
    title = title.replace("_", " ").strip()
    if not title:
        return None
    namespace_probe = title[:-1] if title.endswith(":") else title
    if ":" in namespace_probe:
        return None
    return title


def fetch_first_paragraph_links(title: str) -> tuple[str, list[LinkTarget]]:
    data = wiki_api(
        {
            "action": "parse",
            "page": title,
            "prop": "text",
            "section": 0,
            "redirects": 1,
        }
    )
    parsed = data.get("parse") or {}
    redirected_to = parsed.get("redirects", [{}])[0].get("to") if parsed.get("redirects") else None
    source_title = redirected_to or parsed.get("title") or title
    text_payload = parsed.get("text") or ""
    html_text = text_payload.get("*", "") if isinstance(text_payload, dict) else str(text_payload)

    parser = FirstParagraphLinkParser()
    parser.feed(html_text)
    hrefs = parser.first_links or []

    links: list[LinkTarget] = []
    seen_ids: set[str] = set()
    for href in hrefs:
        link_title = title_from_wiki_href(href)
        if not link_title:
            continue
        topic_id = slugify(link_title)
        if topic_id in seen_ids:
            continue
        seen_ids.add(topic_id)
        links.append(LinkTarget(title=link_title, topic_id=topic_id, rank=len(links) + 1))
    return source_title, links


def load_source_topics(connection: psycopg.Connection[Any], include_placeholders: bool, only_missing_edges: bool) -> list[TopicSeed]:
    status_filter = "" if include_placeholders else "and generation_version is distinct from 'wikipedia-placeholder-v1'"
    missing_filter = (
        "and not exists (select 1 from topic_edges e where e.from_topic_id = topics.id and e.reason = 'wikipedia_first_paragraph_link')"
        if only_missing_edges
        else ""
    )
    sql = f"""
        select id, title, coalesce(canonical_wikipedia_title, title) as wikipedia_title
        from topics
        where generation_status <> 'failed'
          and quality_status in ('approved', 'prototype_pass', 'needs_review')
          {status_filter}
          {missing_filter}
        order by id;
    """
    with connection.cursor() as cursor:
        cursor.execute(sql)
        return [TopicSeed(id=row[0], title=row[1], wikipedia_title=row[2]) for row in cursor.fetchall()]


def existing_topic_ids(connection: psycopg.Connection[Any]) -> set[str]:
    with connection.cursor() as cursor:
        cursor.execute("select id from topics;")
        return {row[0] for row in cursor.fetchall()}


def upsert_placeholder_topics(connection: psycopg.Connection[Any], targets: list[LinkTarget], known_ids: set[str]) -> int:
    inserted = 0
    with connection.cursor() as cursor:
        for target in targets:
            if target.topic_id in known_ids:
                continue
            cursor.execute(
                """
                insert into topics (
                  id, slug, title, canonical_wikipedia_title, pillar, short_explanation,
                  hook_type, hook_text, reading_seconds, source_confidence, quality_status,
                  review_status, risk_level, image_strategy, generation_status, generation_version,
                  generation_hash
                ) values (
                  %s, %s, %s, %s, 'society', %s,
                  'placeholder', %s, 12, 0.600, 'prototype_pass',
                  'auto_checked', 'low', 'pillar_background', 'ready', 'wikipedia-placeholder-v1',
                  %s
                )
                on conflict (id) do nothing;
                """,
                (
                    target.topic_id,
                    target.topic_id,
                    target.title,
                    target.title,
                    PLACEHOLDER_EXPLANATION,
                    PLACEHOLDER_HOOK,
                    seed_sql.stable_uuid("placeholder_topic", target.topic_id, target.title),
                ),
            )
            if cursor.rowcount > 0:
                known_ids.add(target.topic_id)
                inserted += 1
    return inserted


def replace_edges(connection: psycopg.Connection[Any], source: TopicSeed, targets: list[LinkTarget]) -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            "delete from topic_edges where from_topic_id = %s and reason = %s;",
            (source.id, EDGE_REASON),
        )
        inserted = 0
        for target in targets:
            if target.topic_id == source.id:
                continue
            strength = max(0.35, round(0.92 - ((target.rank - 1) * 0.035), 3))
            edge_id = seed_sql.stable_uuid(EDGE_REASON, source.id, target.topic_id, "neighbor")
            evidence = f"{source.wikipedia_title} first paragraph link #{target.rank}: {target.title}"
            cursor.execute(
                """
                insert into topic_edges (
                  id, from_topic_id, to_topic_id, edge_type, strength, reason, status,
                  rank, confidence, source_evidence, generation_status, generation_version, generation_hash
                ) values (
                  %s::uuid, %s, %s, 'neighbor', %s, %s, 'approved',
                  %s, %s, %s, 'ready', %s, %s
                )
                on conflict (from_topic_id, to_topic_id, edge_type) do update set
                  strength = excluded.strength,
                  reason = excluded.reason,
                  status = excluded.status,
                  rank = excluded.rank,
                  confidence = excluded.confidence,
                  source_evidence = excluded.source_evidence,
                  generation_status = excluded.generation_status,
                  generation_version = excluded.generation_version,
                  generation_hash = excluded.generation_hash;
                """,
                (
                    edge_id,
                    source.id,
                    target.topic_id,
                    strength,
                    EDGE_REASON,
                    target.rank,
                    strength,
                    evidence,
                    GENERATION_VERSION,
                    seed_sql.stable_uuid(GENERATION_VERSION, source.id, target.topic_id, target.rank),
                ),
            )
            inserted += 1
        return inserted


def sync_edges(
    database_url: str,
    *,
    include_placeholders: bool,
    only_missing_edges: bool,
    limit: int | None,
    delay: float,
    dry_run: bool,
) -> dict[str, int | str]:
    stats = {
        "source_topics": 0,
        "source_topics_processed": 0,
        "placeholder_topics_inserted": 0,
        "edges_written": 0,
        "fetch_failures": 0,
    }
    with psycopg.connect(validate_database_url(database_url), prepare_threshold=None) as connection:
        sources = load_source_topics(
            connection,
            include_placeholders=include_placeholders,
            only_missing_edges=only_missing_edges,
        )
        if limit is not None:
            sources = sources[:limit]
        known_ids = existing_topic_ids(connection)
        stats["source_topics"] = len(sources)

        for index, source in enumerate(sources, start=1):
            try:
                normalized_title, targets = fetch_first_paragraph_links(source.wikipedia_title)
            except Exception as exc:  # noqa: BLE001 - keep batch moving and report count.
                print(f"warn: failed {source.wikipedia_title}: {exc}")
                stats["fetch_failures"] += 1
                continue

            normalized_source = TopicSeed(source.id, source.title, normalized_title)
            if dry_run:
                print(f"{source.id}: {len(targets)} first-paragraph links")
            else:
                stats["placeholder_topics_inserted"] += upsert_placeholder_topics(connection, targets, known_ids)
                stats["edges_written"] += replace_edges(connection, normalized_source, targets)
                connection.commit()
            stats["source_topics_processed"] += 1
            print(f"{index}/{len(sources)} {source.id}: {len(targets)} links")
            if index < len(sources) and delay > 0:
                time.sleep(delay)
    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync topic_edges from Wikipedia first paragraph links.")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--include-placeholders", action="store_true", help="Also expand placeholder topics from prior runs.")
    parser.add_argument("--only-missing-edges", action="store_true", help="Only expand topics with no first-paragraph edges yet.")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--delay", type=float, default=0.1)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(args.env_file)
    database_url = args.database_url or os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")
    started = dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()
    stats = sync_edges(
        database_url,
        include_placeholders=args.include_placeholders,
        only_missing_edges=args.only_missing_edges,
        limit=args.limit,
        delay=args.delay,
        dry_run=args.dry_run,
    )
    stats["started_at"] = started
    print(json.dumps(stats, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
