#!/usr/bin/env python3
"""Validate and summarize a Wikis seed graph."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Wikis seed graph JSON.")
    parser.add_argument("graph", nargs="?", type=Path, default=Path("data/graph/seed_graph.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    topic_ids = {topic["id"] for topic in graph["topics"]}
    issues: list[str] = []

    for edge in graph["edges"]:
        if edge["from"] not in topic_ids:
            issues.append(f"edge_missing_from:{edge['id']}")
        if edge["to"] not in topic_ids:
            issues.append(f"edge_missing_to:{edge['id']}")

    for topic_id, gestures in graph["gestureIndex"].items():
        if topic_id not in topic_ids:
            issues.append(f"gesture_unknown_topic:{topic_id}")
        for gesture in ["down", "right", "left"]:
            if not gestures.get(gesture):
                issues.append(f"{topic_id}:missing_{gesture}")
            for target in gestures.get(gesture, []):
                if target not in topic_ids:
                    issues.append(f"{topic_id}:{gesture}:unknown_target:{target}")

    if not 100 <= len(graph["topics"]) <= 300:
        issues.append(f"topic_count_out_of_range:{len(graph['topics'])}")
    if len(graph.get("starterPool", [])) < 25:
        issues.append(f"starter_pool_too_small:{len(graph.get('starterPool', []))}")

    for topic in graph["topics"]:
        if topic.get("qualityStatus") != "prototype_pass":
            issues.append(f"{topic['id']}:not_prototype_pass:{topic.get('qualityStatus')}")
        image = topic.get("image", {})
        if image.get("strategy") == "wikipedia_image" and not image.get("selected"):
            issues.append(f"{topic['id']}:missing_selected_image")
        if image.get("strategy") == "pillar_background" and not image.get("fallbackPillar"):
            issues.append(f"{topic['id']}:missing_fallback_pillar")

    edge_types = Counter(edge["type"] for edge in graph["edges"])
    pillars = Counter(topic["pillar"] for topic in graph["topics"])
    if len(pillars) < 4:
        issues.append(f"too_few_pillars:{dict(pillars)}")
    for pillar, count in pillars.items():
        if count / max(len(graph["topics"]), 1) > 0.50:
            issues.append(f"pillar_imbalance:{pillar}:{count}")

    for start_id in graph.get("starterPool", [])[:25]:
        path = rabbit_hole_path(graph, start_id, length=10)
        if len(path) < 10:
            issues.append(f"{start_id}:rabbit_hole_dead_end:{len(path)}")

    print(f"graph: {args.graph}")
    print(f"topics: {len(graph['topics'])}")
    print(f"edges: {len(graph['edges'])}")
    print(f"candidate_queue: {len(graph.get('candidateQueue', []))}")
    print(f"pillars: {dict(sorted(pillars.items()))}")
    print(f"edge_types: {dict(sorted(edge_types.items()))}")
    print(f"starter_pool: {len(graph.get('starterPool', []))}")
    print(f"issues: {len(issues)}")
    for issue in issues[:50]:
        print(f"- {issue}")

    return 1 if issues else 0


def rabbit_hole_path(graph: dict, start_id: str, length: int) -> list[str]:
    path = [start_id]
    current = start_id
    for gesture in ["down", "right", "left", "down", "right", "down", "left", "right", "down"]:
        if len(path) >= length:
            break
        targets = graph.get("gestureIndex", {}).get(current, {}).get(gesture, [])
        next_id = next((target for target in targets if target not in path), None) or (targets[0] if targets else None)
        if not next_id:
            break
        path.append(next_id)
        current = next_id
    return path


if __name__ == "__main__":
    raise SystemExit(main())
