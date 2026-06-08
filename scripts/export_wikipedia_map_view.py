#!/usr/bin/env python3
"""Export the current Supabase Wikis graph as a Wikipedia Map-style HTML view."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

import psycopg


PLACEHOLDER_VERSION = "wikipedia-placeholder-v1"


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


def display_label(title: str, max_chars: int = 20) -> str:
    words = title.split()
    if not words:
        return title
    lines = [words[0]]
    for word in words[1:]:
        if len(lines[-1]) + 1 + len(word) > max_chars:
            lines.append(word)
        else:
            lines[-1] += f" {word}"
    return "\n".join(lines)


def css_escape(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-")


def load_graph(database_url: str) -> dict[str, Any]:
    with psycopg.connect(validate_database_url(database_url), prepare_threshold=None) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select
                  id,
                  title,
                  coalesce(canonical_wikipedia_title, title) as wikipedia_title,
                  pillar,
                  generation_version,
                  quality_status
                from topics
                where generation_status <> 'failed'
                  and quality_status in ('approved', 'prototype_pass', 'needs_review')
                order by id;
                """
            )
            topic_rows = cursor.fetchall()
            cursor.execute(
                """
                select
                  from_topic_id,
                  to_topic_id,
                  edge_type,
                  coalesce(rank, 9999) as rank,
                  coalesce(strength, 0.5) as strength,
                  coalesce(source_evidence, reason) as evidence
                from topic_edges
                where status = 'approved'
                order by from_topic_id, rank, to_topic_id;
                """
            )
            edge_rows = cursor.fetchall()

    topic_ids = {row[0] for row in topic_rows}
    incoming: dict[str, int] = {topic_id: 0 for topic_id in topic_ids}
    outgoing: dict[str, int] = {topic_id: 0 for topic_id in topic_ids}
    for from_id, to_id, *_ in edge_rows:
        if from_id in topic_ids and to_id in topic_ids:
            outgoing[from_id] += 1
            incoming[to_id] += 1

    nodes = []
    for topic_id, title, wikipedia_title, pillar, generation_version, quality_status in topic_rows:
        is_placeholder = generation_version == PLACEHOLDER_VERSION
        is_source = outgoing.get(topic_id, 0) > 0
        color = "#03A9F4" if is_source else "#90CAF9"
        if is_placeholder:
            color = "#B3E5FC" if not is_source else "#4FC3F7"
        if topic_id == "black-hole":
            color = "#FFC107"
        nodes.append(
            {
                "id": topic_id,
                "label": display_label(title),
                "title": (
                    f"<strong>{title}</strong><br>"
                    f"Wikipedia: {wikipedia_title}<br>"
                    f"Pillar: {pillar}<br>"
                    f"Outgoing edges: {outgoing.get(topic_id, 0)}<br>"
                    f"Incoming edges: {incoming.get(topic_id, 0)}<br>"
                    f"Quality: {quality_status}<br>"
                    f"{'Placeholder topic' if is_placeholder else 'Generated topic'}"
                ),
                "value": 6 + min(24, incoming.get(topic_id, 0) + outgoing.get(topic_id, 0)),
                "color": {
                    "background": color,
                    "border": "#0288D1" if topic_id != "black-hole" else "#C79100",
                    "highlight": {"background": "#FFC107", "border": "#D39E00"},
                },
                "font": {"size": 16 if is_source else 13},
                "group": "source" if is_source else "placeholder" if is_placeholder else "topic",
            }
        )

    edges = []
    for from_id, to_id, edge_type, rank, strength, evidence in edge_rows:
        if from_id not in topic_ids or to_id not in topic_ids:
            continue
        edges.append(
            {
                "id": f"{css_escape(from_id)}__{css_escape(edge_type)}__{css_escape(to_id)}",
                "from": from_id,
                "to": to_id,
                "arrows": "to",
                "width": 1 + (float(strength) * 2),
                "color": {"color": "#4BA3C7", "highlight": "#FFC107"},
                "title": f"{evidence}<br>Rank: {rank}<br>Strength: {strength}",
            }
        )

    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "topics": len(nodes),
            "edges": len(edges),
            "sourceTopics": sum(1 for value in outgoing.values() if value > 0),
            "placeholderTopics": sum(1 for row in topic_rows if row[4] == PLACEHOLDER_VERSION),
        },
    }


def html_document(graph: dict[str, Any]) -> str:
    payload = json.dumps(graph, ensure_ascii=False)
    stats = graph["stats"]
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Wikis Current Wikipedia Map</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/vis/4.16.1/vis.css" type="text/css">
  <link rel="stylesheet" href="../css/style.css" type="text/css">
  <style>
    #container {{ background: #f8fbfd; }}
    #summary {{
      position: fixed;
      top: 14px;
      left: 14px;
      z-index: 10;
      max-width: 360px;
      padding: 12px 14px;
      border-radius: 8px;
      color: rgba(0, 0, 0, 0.72);
      font-size: 14px;
      line-height: 1.35;
    }}
    #summary h1 {{
      margin: 0 0 6px;
      font-size: 17px;
      line-height: 1.2;
    }}
    #summary p {{ margin: 4px 0; }}
    #summary button {{
      margin-top: 8px;
      border: 1px solid rgba(0,0,0,0.14);
      background: white;
      border-radius: 6px;
      padding: 6px 9px;
      cursor: pointer;
    }}
  </style>
</head>
<body>
  <div id="summary" class="transparent-blur">
    <h1>Wikis Current Map</h1>
    <p>{stats["topics"]} topics, {stats["edges"]} first-paragraph edges.</p>
    <p>{stats["sourceTopics"]} expanded source topics, {stats["placeholderTopics"]} placeholder topics.</p>
    <button id="fit">Fit graph</button>
    <button id="focus">Focus Black Hole</button>
  </div>
  <div id="container" class="fullscreen"></div>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/vis/4.16.1/vis-network.min.js"></script>
  <script>
    const graph = {payload};
    const nodes = new vis.DataSet(graph.nodes);
    const edges = new vis.DataSet(graph.edges);
    const network = new vis.Network(
      document.getElementById('container'),
      {{ nodes, edges }},
      {{
        nodes: {{
          shape: 'dot',
          scaling: {{ min: 8, max: 34, label: {{ enabled: true, min: 10, max: 22, drawThreshold: 7, maxVisible: 28 }} }},
          font: {{ face: getComputedStyle(document.body).fontFamily, color: 'rgba(0,0,0,0.78)' }}
        }},
        edges: {{
          smooth: {{ type: 'continuous' }},
          hoverWidth: 0,
          selectionWidth: 2
        }},
        interaction: {{
          hover: true,
          tooltipDelay: 80,
          hoverConnectedEdges: true,
          navigationButtons: true,
          keyboard: true
        }},
        physics: {{
          stabilization: {{ iterations: 900 }},
          barnesHut: {{
            gravitationalConstant: -18000,
            centralGravity: 0.18,
            springLength: 120,
            springConstant: 0.018,
            damping: 0.32,
            avoidOverlap: 0.28
          }}
        }}
      }}
    );

    document.getElementById('fit').addEventListener('click', () => {{
      network.fit({{ animation: {{ duration: 600, easingFunction: 'easeInOutQuad' }} }});
    }});
    document.getElementById('focus').addEventListener('click', () => {{
      network.focus('black-hole', {{ scale: 0.9, animation: {{ duration: 700, easingFunction: 'easeInOutQuad' }} }});
      network.selectNodes(['black-hole']);
    }});
    network.once('stabilizationIterationsDone', () => network.fit());
  </script>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export current Supabase graph into wikipedia-map/graphs.")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--out", type=Path, default=Path("wikipedia-map/graphs/current-supabase-map.html"))
    parser.add_argument("--json-out", type=Path, default=Path("wikipedia-map/graphs/current-supabase-map.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(args.env_file)
    database_url = args.database_url or os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")
    graph = load_graph(database_url)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html_document(graph), encoding="utf-8")
    args.json_out.write_text(json.dumps(graph, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"html": str(args.out), "json": str(args.json_out), **graph["stats"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
