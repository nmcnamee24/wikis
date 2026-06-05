#!/usr/bin/env python3
"""Build a Wikis seed knowledge graph from generated card JSON files."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


MANUAL_EDGES: dict[str, dict[str, list[str]]] = {
    "black-hole": {
        "deeper": ["event-horizon"],
        "neighbor": ["neutron-star", "fermi-paradox", "saturn"],
    },
    "event-horizon": {
        "deeper": ["black-hole"],
        "neighbor": ["fermi-paradox", "neutron-star"],
    },
    "neutron-star": {
        "deeper": ["black-hole"],
        "neighbor": ["saturn", "fermi-paradox"],
    },
    "saturn": {
        "deeper": ["plate-tectonics"],
        "neighbor": ["neutron-star", "black-hole"],
    },
    "plate-tectonics": {
        "deeper": ["pompeii"],
        "neighbor": ["saturn"],
    },
    "fermi-paradox": {
        "deeper": ["black-hole"],
        "neighbor": ["game-theory", "saturn"],
    },
    "octopus": {
        "deeper": ["cognitive-bias"],
        "neighbor": ["myth"],
    },
    "epic-of-gilgamesh": {
        "deeper": ["myth"],
        "neighbor": ["homer", "library-of-alexandria"],
    },
    "myth": {
        "deeper": ["epic-of-gilgamesh"],
        "neighbor": ["homer", "octopus"],
    },
    "homer": {
        "deeper": ["epic-of-gilgamesh"],
        "neighbor": ["myth", "library-of-alexandria"],
    },
    "printing-press": {
        "deeper": ["library-of-alexandria"],
        "neighbor": ["magna-carta", "homer"],
    },
    "library-of-alexandria": {
        "deeper": ["epic-of-gilgamesh"],
        "neighbor": ["homer", "printing-press", "ancient-rome"],
    },
    "ancient-rome": {
        "deeper": ["julius-caesar", "pompeii"],
        "neighbor": ["silk-road", "library-of-alexandria"],
    },
    "julius-caesar": {
        "deeper": ["ancient-rome"],
        "neighbor": ["pompeii", "magna-carta"],
    },
    "pompeii": {
        "deeper": ["ancient-rome"],
        "neighbor": ["julius-caesar", "plate-tectonics"],
    },
    "silk-road": {
        "deeper": ["ancient-rome"],
        "neighbor": ["library-of-alexandria", "magna-carta"],
    },
    "magna-carta": {
        "deeper": ["democracy"],
        "neighbor": ["julius-caesar", "printing-press"],
    },
    "democracy": {
        "deeper": ["magna-carta"],
        "neighbor": ["game-theory", "cognitive-bias"],
    },
    "cognitive-bias": {
        "deeper": ["game-theory"],
        "neighbor": ["democracy", "octopus"],
    },
    "game-theory": {
        "deeper": ["cognitive-bias"],
        "neighbor": ["democracy", "fermi-paradox"],
    },
}


TELEPORT_BY_PILLAR = {
    "science": ["silk-road", "epic-of-gilgamesh", "democracy"],
    "literature": ["black-hole", "ancient-rome", "cognitive-bias"],
    "culture": ["black-hole", "ancient-rome", "cognitive-bias"],
    "society": ["saturn", "homer", "ancient-rome"],
    "history": ["black-hole", "octopus", "game-theory"],
}


EDGE_REASON = {
    "deeper": "manual_rabbit_hole",
    "neighbor": "manual_neighborhood",
    "teleport": "cross_pillar_curiosity",
    "candidate": "wikipedia_mapped_candidate",
}


def slugify(value: str) -> str:
    value = value.lower().replace("&", " and ")
    value = re.sub(r"\([^)]*\)", "", value)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "topic"


def load_cards(cards_dir: Path) -> dict[str, dict[str, Any]]:
    cards: dict[str, dict[str, Any]] = {}
    for path in sorted(cards_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["quality"]["status"] != "prototype_pass":
            continue
        topic_id = slugify(data["source"]["wikipediaTitle"])
        cards[topic_id] = data
    return cards


def topic_record(topic_id: str, data: dict[str, Any]) -> dict[str, Any]:
    card = data["card"]
    source = data["source"]
    image = data["image"]
    return {
        "id": topic_id,
        "title": card["title"],
        "pillar": card["pillar"],
        "explanation": card["explanation"],
        "hookType": card["hookType"],
        "hook": card["hook"],
        "readingSeconds": card["readingSeconds"],
        "qualityStatus": data["quality"]["status"],
        "wikipedia": {
            "title": source["wikipediaTitle"],
            "pageId": source["pageId"],
            "revisionId": source["revisionId"],
        },
        "image": image,
    }


def add_edge(
    edges: dict[tuple[str, str, str], dict[str, Any]],
    source: str,
    target: str,
    edge_type: str,
    strength: float,
    reason: str | None = None,
) -> None:
    if source == target:
        return
    key = (source, target, edge_type)
    edges[key] = {
        "id": f"{source}__{edge_type}__{target}",
        "from": source,
        "to": target,
        "type": edge_type,
        "strength": round(strength, 3),
        "reason": reason or EDGE_REASON.get(edge_type, "seed_graph"),
    }


def build_edges(cards: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    known_ids = set(cards)
    title_to_id: dict[str, str] = {}
    for tid in known_ids:
        source = cards[tid]["source"]
        title_to_id[source["wikipediaTitle"].lower()] = tid
        title_to_id[source["requestedTitle"].lower()] = tid
    edges: dict[tuple[str, str, str], dict[str, Any]] = {}
    candidate_queue: dict[str, dict[str, Any]] = {}

    for source_id, by_type in MANUAL_EDGES.items():
        if source_id not in known_ids:
            continue
        for edge_type, targets in by_type.items():
            for index, target_id in enumerate(targets):
                if target_id in known_ids:
                    add_edge(edges, source_id, target_id, edge_type, 1.0 - (index * 0.05))

    for source_id, data in cards.items():
        candidates = data["mapping"].get("leadOrFallbackLinks") or data["mapping"].get("firstParagraphLinks") or []
        for index, link in enumerate(candidates[:12]):
            target_id = title_to_id.get(link["title"].lower()) or slugify(link["title"])
            if target_id in known_ids:
                add_edge(edges, source_id, target_id, "neighbor", 0.72 - (index * 0.02), "wikipedia_mapped_known_topic")
            else:
                candidate_queue.setdefault(
                    target_id,
                    {
                        "id": target_id,
                        "title": link["title"],
                        "source": "wikipedia_lead_link",
                        "seenFrom": [],
                        "priority": 0,
                    },
                )
                candidate_queue[target_id]["seenFrom"].append(source_id)
                candidate_queue[target_id]["priority"] += max(1, 12 - index)

    for source_id, data in cards.items():
        pillar = data["card"]["pillar"]
        for index, target_id in enumerate(TELEPORT_BY_PILLAR.get(pillar, [])):
            if target_id in known_ids:
                add_edge(edges, source_id, target_id, "teleport", 0.92 - (index * 0.05))

    add_prototype_fallback_edges(cards, edges, title_to_id)

    return sorted(edges.values(), key=lambda edge: edge["id"]), sorted(
        candidate_queue.values(),
        key=lambda candidate: (-candidate["priority"], candidate["title"]),
    )


def add_prototype_fallback_edges(
    cards: dict[str, dict[str, Any]],
    edges: dict[tuple[str, str, str], dict[str, Any]],
    title_to_id: dict[str, str],
) -> None:
    known_ids = set(cards)
    by_pillar: dict[str, list[str]] = defaultdict(list)
    for topic_id, data in cards.items():
        by_pillar[data["card"]["pillar"]].append(topic_id)
    for topics in by_pillar.values():
        topics.sort()

    outgoing: dict[str, dict[str, list[str]]] = {
        topic_id: {"deeper": [], "neighbor": [], "teleport": []}
        for topic_id in known_ids
    }
    for edge in edges.values():
        if edge["type"] in outgoing[edge["from"]]:
            outgoing[edge["from"]][edge["type"]].append(edge["to"])

    for source_id, data in cards.items():
        pillar = data["card"]["pillar"]
        mapped = []
        candidates = data["mapping"].get("leadOrFallbackLinks") or data["mapping"].get("firstParagraphLinks") or []
        for link in candidates:
            target_id = title_to_id.get(link["title"].lower()) or slugify(link["title"])
            if target_id in known_ids and target_id != source_id and target_id not in mapped:
                mapped.append(target_id)
        same_pillar = [topic_id for topic_id in by_pillar[pillar] if topic_id != source_id]
        any_topic = [topic_id for topic_id in sorted(known_ids) if topic_id != source_id]

        if not outgoing[source_id]["deeper"]:
            target_id = first_available(mapped, same_pillar, any_topic)
            if target_id:
                add_edge(edges, source_id, target_id, "deeper", 0.52, "prototype_deeper_fallback")
                outgoing[source_id]["deeper"].append(target_id)

        if not outgoing[source_id]["neighbor"]:
            targets = first_n_available(3, mapped, same_pillar, any_topic)
            for index, target_id in enumerate(targets):
                add_edge(edges, source_id, target_id, "neighbor", 0.48 - (index * 0.03), "prototype_neighbor_fallback")
                outgoing[source_id]["neighbor"].append(target_id)

        if not outgoing[source_id]["teleport"]:
            cross_pillar = [
                topic_id
                for topic_id in sorted(known_ids)
                if topic_id != source_id and cards[topic_id]["card"]["pillar"] != pillar
            ]
            target_id = first_available(cross_pillar, any_topic)
            if target_id:
                add_edge(edges, source_id, target_id, "teleport", 0.45, "prototype_teleport_fallback")
                outgoing[source_id]["teleport"].append(target_id)


def first_available(*groups: list[str]) -> str | None:
    for group in groups:
        if group:
            return group[0]
    return None


def first_n_available(count: int, *groups: list[str]) -> list[str]:
    out: list[str] = []
    for group in groups:
        for item in group:
            if item not in out:
                out.append(item)
            if len(out) >= count:
                return out
    return out


def build_gesture_index(topics: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, dict[str, list[str]]]:
    index: dict[str, dict[str, list[str]]] = {
        topic["id"]: {"down": [], "right": [], "left": []}
        for topic in topics
    }
    edge_to_gesture = {"deeper": "down", "prerequisite": "down", "neighbor": "right", "contrast": "right", "person": "right", "place": "right", "teleport": "left"}
    for edge in sorted(edges, key=lambda item: item["strength"], reverse=True):
        gesture = edge_to_gesture.get(edge["type"])
        if gesture:
            bucket = index[edge["from"]][gesture]
            if edge["to"] not in bucket:
                bucket.append(edge["to"])
    return index


def validate_graph(topics: list[dict[str, Any]], gesture_index: dict[str, dict[str, list[str]]]) -> list[str]:
    issues: list[str] = []
    for topic in topics:
        topic_id = topic["id"]
        for gesture, label in {"down": "missing_down", "right": "missing_right", "left": "missing_left"}.items():
            if not gesture_index[topic_id][gesture]:
                issues.append(f"{topic_id}:{label}")
    return issues


def build_graph(cards_dir: Path) -> dict[str, Any]:
    cards = load_cards(cards_dir)
    topics = [topic_record(topic_id, data) for topic_id, data in sorted(cards.items())]
    edges, candidate_queue = build_edges(cards)
    gesture_index = build_gesture_index(topics, edges)
    issues = validate_graph(topics, gesture_index)
    starter_pool = [
        topic["id"]
        for topic in topics
        if topic["qualityStatus"] == "prototype_pass"
    ]
    starter_pool.sort(key=lambda topic_id: (cards[topic_id]["card"]["pillar"], topic_id))
    pillar_counts: dict[str, int] = defaultdict(int)
    for topic in topics:
        pillar_counts[topic["pillar"]] += 1

    return {
        "schemaVersion": 1,
        "graphId": "wikis-seed-v0",
        "description": "Prototype seed graph generated from Step 01 Wikipedia cards.",
        "topics": topics,
        "edges": edges,
        "gestureIndex": gesture_index,
        "starterPool": starter_pool,
        "candidateQueue": candidate_queue[:100],
        "stats": {
            "topicCount": len(topics),
            "edgeCount": len(edges),
            "candidateQueueCount": len(candidate_queue),
            "pillarCounts": dict(sorted(pillar_counts.items())),
            "validationIssues": issues,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Wikis seed graph JSON.")
    parser.add_argument("--cards-dir", type=Path, default=Path("data/cards"))
    parser.add_argument("--out", type=Path, default=Path("data/graph/seed_graph.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    graph = build_graph(args.cards_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(graph, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    print(json.dumps(graph["stats"], indent=2))
    return 1 if graph["stats"]["validationIssues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
