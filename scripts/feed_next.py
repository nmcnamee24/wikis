#!/usr/bin/env python3
"""Resolve the next Wikis feed topic from explicit Supabase edges."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


GESTURE_EDGE_TYPES = {
    "down": ["deeper", "prerequisite"],
    "right": ["neighbor", "contrast", "person", "place"],
    "left": ["teleport"],
}

REASON_CODES = {
    ("down", "deeper"): "best_deeper_edge",
    ("down", "prerequisite"): "best_prerequisite_edge",
    ("right", "neighbor"): "best_neighbor_edge",
    ("right", "person"): "best_neighbor_edge",
    ("right", "place"): "best_neighbor_edge",
    ("right", "contrast"): "best_contrast_edge",
    ("left", "teleport"): "best_teleport_edge",
}

SENSITIVE_TERMS = {"assassination", "war", "disease", "death", "violence"}


def load_request(args: argparse.Namespace) -> dict[str, Any]:
    if args.request_json:
        return json.loads(args.request_json)
    if args.request_file:
        return json.loads(args.request_file.read_text(encoding="utf-8"))
    return {
        "currentTopicId": args.current_topic,
        "gesture": args.gesture,
        "exploredTopicIds": args.explored_topic_ids or [],
        "savedTopicIds": args.saved_topic_ids or [],
        "allowPrototypeContent": args.allow_prototype_content,
    }


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


def load_graph_from_database(database_url: str) -> dict[str, Any]:
    sql = r"""
with topic_rows as (
  select jsonb_build_object(
    'id', t.id,
    'title', t.title,
    'pillar', t.pillar,
    'explanation', t.short_explanation,
    'hookType', t.hook_type,
    'hook', t.hook_text,
    'readingSeconds', t.reading_seconds,
    'qualityStatus', t.quality_status,
    'wikipedia', jsonb_build_object(
      'title', t.canonical_wikipedia_title,
      'pageId', s.wikipedia_page_id,
      'revisionId', s.wikipedia_revision_id
    ),
    'image', jsonb_build_object(
      'strategy', t.image_strategy,
      'selected', case
        when a.asset_type = 'wikipedia_image' then jsonb_build_object(
          'source', 'wikipedia_image',
          'title', ic.source_title,
          'url', coalesce(a.url, ic.url),
          'thumbnailUrl', coalesce(a.thumbnail_url, ic.thumbnail_url),
          'width', ic.width,
          'height', ic.height,
          'qualityScore', coalesce(a.quality_score, ic.quality_score, 0.75),
          'rejectionReasons', '[]'::jsonb
        )
        else null
      end,
      'fallbackPillar', case when a.asset_type = 'pillar_background' then coalesce(a.pillar, t.pillar) else null end,
      'reason', case when a.asset_type = 'pillar_background' then 'pillar_background' else null end
    )
  ) as item
  from topics t
  left join lateral (
    select *
    from topic_source_snapshots s
    where s.topic_id = t.id
    order by s.created_at desc
    limit 1
  ) s on true
  left join topic_assets a on a.id = t.image_asset_id
  left join image_candidates ic on ic.id = a.image_candidate_id
  where t.quality_status in ('approved', 'prototype_pass', 'needs_review')
    and t.generation_status <> 'failed'
),
edge_rows as (
  select jsonb_build_object(
    'id', coalesce(e.from_topic_id || '__' || e.edge_type || '__' || e.to_topic_id, e.id::text),
    'from', e.from_topic_id,
    'to', e.to_topic_id,
    'type', e.edge_type,
    'strength', e.strength,
    'reason', e.reason,
    'rank', e.rank,
    'confidence', e.confidence,
    'generationStatus', e.generation_status,
    'generationVersion', e.generation_version,
    'generationHash', e.generation_hash
  ) as item
  from topic_edges e
  join topics t on t.id = e.to_topic_id
  where e.status = 'approved'
    and t.quality_status in ('approved', 'prototype_pass', 'needs_review')
    and t.generation_status <> 'failed'
)
select jsonb_build_object(
  'schemaVersion', 1,
  'graphId', 'supabase-live',
  'description', 'Wikis graph loaded from Supabase Postgres.',
  'topics', coalesce((select jsonb_agg(item) from topic_rows), '[]'::jsonb),
  'edges', coalesce((select jsonb_agg(item) from edge_rows), '[]'::jsonb),
  'stats', jsonb_build_object(
    'topicCount', (select count(*) from topic_rows),
    'edgeCount', (select count(*) from edge_rows),
    'pillarCounts', '{}',
    'validationIssues', '[]'::jsonb
  )
)::text;
"""
    try:
        import psycopg  # type: ignore

        with psycopg.connect(validate_database_url(database_url)) as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql)
                row = cursor.fetchone()
                if not row:
                    raise RuntimeError("database graph query returned no rows")
                value = row[0]
                return value if isinstance(value, dict) else json.loads(value)
    except ModuleNotFoundError:
        result = subprocess.run(
            ["psql", validate_database_url(database_url), "-v", "ON_ERROR_STOP=1", "-Atc", sql],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout)


def topic_by_id(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {topic["id"]: topic for topic in graph["topics"]}


def is_visible(topic: dict[str, Any], allow_prototype: bool) -> bool:
    return topic.get("qualityStatus") == "approved" or (
        allow_prototype and topic.get("qualityStatus") in {"prototype_pass", "needs_review"}
    )


def visual_strength(topic: dict[str, Any]) -> float:
    image = topic.get("image", {})
    if image.get("strategy") == "wikipedia_image":
        return float((image.get("selected") or {}).get("qualityScore") or 0.75)
    return 0.48


def source_confidence(topic: dict[str, Any]) -> float:
    return 0.92 if topic.get("wikipedia", {}).get("revisionId") is not None else 0.68


def quality_score(topic: dict[str, Any]) -> float:
    return {
        "approved": 1.0,
        "prototype_pass": 0.86,
        "needs_review": 0.58,
    }.get(topic.get("qualityStatus"), 0.0)


def novelty_score(topic: dict[str, Any], current: dict[str, Any] | None, explored: set[str], saved: set[str]) -> float:
    score = 0.72
    if current and current.get("pillar") != topic.get("pillar"):
        score += 0.20
    if topic["id"] in saved:
        score -= 0.10
    if topic["id"] in explored:
        score -= 0.35
    return min(max(score, 0.0), 1.0)


def repetition_penalty(topic_id: str, explored_ordered: list[str]) -> float:
    for offset, seen_id in enumerate(reversed(explored_ordered)):
        if seen_id == topic_id:
            if offset <= 2:
                return 0.75
            if offset <= 7:
                return 0.35
            return 0.12
    return 0.0


def sensitivity_penalty(topic: dict[str, Any]) -> float:
    text = f"{topic.get('title', '')} {topic.get('explanation', '')}".lower()
    return 0.08 if any(term in text for term in SENSITIVE_TERMS) else 0.0


def edge_type_bonus(edge_type: str, gesture: str) -> float:
    if (gesture, edge_type) in {("down", "deeper"), ("right", "neighbor"), ("left", "teleport")}:
        return 0.08
    if (gesture, edge_type) in {("down", "prerequisite"), ("right", "contrast")}:
        return 0.04
    if gesture == "right" and edge_type in {"person", "place"}:
        return 0.03
    return 0.0


def score_candidate(
    edge: dict[str, Any],
    topic: dict[str, Any],
    current: dict[str, Any] | None,
    gesture: str,
    explored_ordered: list[str],
    saved: set[str],
) -> float:
    explored = set(explored_ordered)
    edge_relevance = min(max(float(edge.get("strength") or 0.0), 0.0), 1.0)
    confidence = float(edge.get("confidence") or edge_relevance)
    topic_quality = quality_score(topic)
    source = source_confidence(topic)
    novelty = novelty_score(topic, current, explored, saved)
    visual = visual_strength(topic)
    saved_affinity = 0.08 if topic["id"] in saved else 0.0
    penalty = repetition_penalty(topic["id"], explored_ordered) + sensitivity_penalty(topic)
    bonus = edge_type_bonus(edge["type"], gesture)

    if gesture == "down":
        return edge_relevance * 0.42 + confidence * 0.14 + topic_quality * 0.16 + source * 0.12 + novelty * 0.08 + visual * 0.04 + bonus + saved_affinity - penalty
    if gesture == "right":
        return edge_relevance * 0.34 + confidence * 0.14 + topic_quality * 0.15 + source * 0.10 + novelty * 0.14 + visual * 0.05 + bonus + saved_affinity - penalty
    return edge_relevance * 0.24 + confidence * 0.10 + topic_quality * 0.14 + source * 0.10 + novelty * 0.30 + visual * 0.07 + bonus + saved_affinity - penalty


def resolve_next(graph: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    topics = topic_by_id(graph)
    current_id = request["currentTopicId"]
    gesture = request["gesture"]
    explored = list(request.get("exploredTopicIds") or [])
    saved = set(request.get("savedTopicIds") or [])
    allow_prototype = bool(request.get("allowPrototypeContent", True))
    current = topics.get(current_id)

    candidates: list[dict[str, Any]] = []
    allowed_edge_types = set(GESTURE_EDGE_TYPES[gesture])
    for edge in graph["edges"]:
        if edge["from"] != current_id or edge["type"] not in allowed_edge_types:
            continue
        if edge.get("generationStatus") == "failed":
            continue
        topic = topics.get(edge["to"])
        if not topic or not is_visible(topic, allow_prototype) or source_confidence(topic) < 0.55:
            continue
        candidates.append(
            {
                "topic": topic,
                "edge": edge,
                "score": score_candidate(edge, topic, current, gesture, explored, saved),
                "reasonCode": REASON_CODES[(gesture, edge["type"])],
            }
        )
    candidates.sort(key=lambda item: (-item["score"], item["topic"]["title"]))

    selected = candidates[0] if candidates else None
    if not selected:
        raise RuntimeError(f"No approved traversal edge from {current_id} for {gesture}")

    selected_topic = selected["topic"]
    selected_edge = selected.get("edge")
    fallback_ids = [item["topic"]["id"] for item in candidates[1:4]]

    return {
        "nextTopicId": selected_topic["id"],
        "nextTopic": selected_topic,
        "reasonCode": selected["reasonCode"],
        "gesture": gesture,
        "score": round(selected["score"], 4),
        "selectedEdgeId": selected_edge["id"] if selected_edge else None,
        "fallbackTopicIds": fallback_ids,
        "fallbackWasUsed": False,
        "debug": {
            "currentTopicId": current_id,
            "candidateCount": len(candidates),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve the next Wikis feed topic.")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--request-json")
    parser.add_argument("--request-file", type=Path)
    parser.add_argument("--current-topic")
    parser.add_argument("--gesture", choices=["down", "right", "left"])
    parser.add_argument("--explored-topic-ids", nargs="*")
    parser.add_argument("--saved-topic-ids", nargs="*")
    parser.add_argument("--allow-prototype-content", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(args.env_file)
    request = load_request(args)
    if not request.get("currentTopicId") or request.get("gesture") not in GESTURE_EDGE_TYPES:
        print("ERROR: provide currentTopicId and gesture", file=sys.stderr)
        return 2
    database_url = args.database_url or os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL is required", file=sys.stderr)
        return 2
    graph = load_graph_from_database(database_url)
    response = resolve_next(graph, request)
    print(json.dumps(response, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
