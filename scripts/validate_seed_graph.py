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

    edge_types = Counter(edge["type"] for edge in graph["edges"])
    pillars = Counter(topic["pillar"] for topic in graph["topics"])

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


if __name__ == "__main__":
    raise SystemExit(main())

