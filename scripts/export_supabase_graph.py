#!/usr/bin/env python3
"""Export a Supabase-backed Wikis graph to an interactive standalone HTML file."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


DEEP_EDGE_TYPES = {"deeper", "prerequisite"}
ADJACENT_EDGE_TYPES = {"neighbor", "contrast", "person", "place"}
PILLAR_COLORS = {
    "science": "#62d2ff",
    "history": "#d8a55a",
    "culture": "#c98cff",
    "society": "#7ee0a5",
    "literature": "#ff8fb3",
    "candidate": "#8f98aa",
}


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


def slugify(value: str) -> str:
    value = value.lower().replace("&", " and ")
    value = re.sub(r"\([^)]*\)", "", value)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "topic"


def fetch_graph(database_url: str, session_id: str | None, anonymous_session_id: str | None) -> dict[str, Any]:
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ModuleNotFoundError as exc:
        raise RuntimeError("psycopg is required. Install requirements.txt first.") from exc

    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select
                  id, title, pillar, quality_status, generation_status,
                  canonical_wikipedia_title, created_at, updated_at
                from topics
                where quality_status in ('approved', 'prototype_pass', 'needs_review')
                  and generation_status <> 'failed'
                order by pillar, title;
                """
            )
            topics = [dict(row) for row in cursor.fetchall()]

            cursor.execute(
                """
                select
                  id::text, from_topic_id, to_topic_id, edge_type, strength,
                  status, rank, confidence, generation_status
                from topic_edges
                where status = 'approved'
                order by from_topic_id, rank nulls last, strength desc;
                """
            )
            topic_edges = [dict(row) for row in cursor.fetchall()]

            cursor.execute(
                """
                select
                  id::text, source, from_topic_id, from_title, to_topic_id, to_title,
                  normalized_to_title, raw_position, extraction_method,
                  candidate_strength, proposed_edge_type, status
                from candidate_edges
                where status = 'pending'
                  and from_topic_id is not null
                order by from_topic_id, raw_position nulls last, candidate_strength desc nulls last;
                """
            )
            candidate_edges = [dict(row) for row in cursor.fetchall()]

            explored: list[dict[str, Any]] = []
            if session_id or anonymous_session_id:
                cursor.execute(
                    """
                    select from_topic_id, to_topic_id, gesture, reason_code, created_at
                    from exploration_events
                    where (%s::text is null or session_id = %s)
                      and (%s::text is null or anonymous_session_id = %s)
                      and (from_topic_id is not null or to_topic_id is not null)
                    order by created_at;
                    """,
                    (session_id, session_id, anonymous_session_id, anonymous_session_id),
                )
                explored = [dict(row) for row in cursor.fetchall()]

    topic_ids = {topic["id"] for topic in topics}
    nodes: dict[str, dict[str, Any]] = {}
    for topic in topics:
        nodes[topic["id"]] = {
            "id": topic["id"],
            "title": topic["title"],
            "pillar": topic["pillar"],
            "qualityStatus": topic["quality_status"],
            "generationStatus": topic["generation_status"],
            "kind": "topic",
            "explored": False,
        }

    edges: list[dict[str, Any]] = []
    for edge in topic_edges:
        if edge["from_topic_id"] not in topic_ids or edge["to_topic_id"] not in topic_ids:
            continue
        edge_type = edge["edge_type"]
        edges.append(
            {
                "id": edge["id"],
                "source": edge["from_topic_id"],
                "target": edge["to_topic_id"],
                "type": edge_type,
                "strength": float(edge["strength"] or 0),
                "kind": "approved",
                "lineStyle": "solid" if edge_type in DEEP_EDGE_TYPES else "dashed",
            }
        )

    for candidate in candidate_edges:
        source_id = candidate["from_topic_id"]
        target_id = candidate["to_topic_id"] or candidate["normalized_to_title"] or slugify(candidate["to_title"])
        if not source_id or source_id not in topic_ids:
            continue
        if target_id not in nodes:
            nodes[target_id] = {
                "id": target_id,
                "title": candidate["to_title"],
                "pillar": "candidate",
                "qualityStatus": "candidate",
                "generationStatus": "missing",
                "kind": "candidate",
                "explored": False,
            }
        edge_type = candidate["proposed_edge_type"] or "neighbor"
        edges.append(
            {
                "id": candidate["id"],
                "source": source_id,
                "target": target_id,
                "type": edge_type,
                "strength": float(candidate["candidate_strength"] or 0.35),
                "kind": "candidate",
                "lineStyle": "solid" if edge_type in DEEP_EDGE_TYPES else "dashed",
            }
        )

    explored_edges: list[dict[str, Any]] = []
    for index, event in enumerate(explored):
        for topic_id in [event.get("from_topic_id"), event.get("to_topic_id")]:
            if topic_id in nodes:
                nodes[topic_id]["explored"] = True
        if event.get("from_topic_id") and event.get("to_topic_id"):
            explored_edges.append(
                {
                    "id": f"explored-{index}",
                    "source": event["from_topic_id"],
                    "target": event["to_topic_id"],
                    "gesture": event.get("gesture"),
                    "reasonCode": event.get("reason_code"),
                }
            )

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "exploredEdges": explored_edges,
        "stats": {
            "topics": len(topics),
            "nodes": len(nodes),
            "approvedEdges": len(topic_edges),
            "candidateEdges": len(candidate_edges),
            "renderedEdges": len(edges),
            "exploredEvents": len(explored),
        },
    }


def html_document(graph: dict[str, Any]) -> str:
    graph_json = json.dumps(graph, ensure_ascii=False)
    colors_json = json.dumps(PILLAR_COLORS)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Wikis Supabase Graph</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #111318;
      --panel: rgba(20, 24, 31, 0.92);
      --text: #f3efe4;
      --muted: #a8afbf;
      --line: #5d6677;
      --explored: #ffd166;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      overflow: hidden;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    #graph {{ width: 100vw; height: 100vh; display: block; }}
    .toolbar {{
      position: fixed;
      top: 14px;
      left: 14px;
      z-index: 4;
      width: min(420px, calc(100vw - 28px));
      padding: 12px;
      background: var(--panel);
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 8px;
      box-shadow: 0 18px 40px rgba(0,0,0,0.28);
    }}
    .toolbar h1 {{
      margin: 0 0 8px;
      font-size: 16px;
      letter-spacing: 0;
    }}
    .meta {{
      margin-bottom: 10px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.35;
    }}
    .controls {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    input, button, label {{
      font: inherit;
      font-size: 13px;
    }}
    input {{
      flex: 1 1 180px;
      min-width: 0;
      padding: 8px 10px;
      border: 1px solid rgba(255,255,255,0.16);
      border-radius: 6px;
      color: var(--text);
      background: rgba(255,255,255,0.06);
    }}
    button {{
      padding: 8px 10px;
      border: 1px solid rgba(255,255,255,0.16);
      border-radius: 6px;
      color: var(--text);
      background: rgba(255,255,255,0.08);
      cursor: pointer;
    }}
    label {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      color: var(--muted);
      padding: 6px 0;
    }}
    .legend {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 6px 12px;
      margin-top: 10px;
      color: var(--muted);
      font-size: 12px;
    }}
    .legend span {{ display: inline-flex; align-items: center; gap: 7px; }}
    .sample {{ width: 26px; height: 0; border-top: 2px solid #b8c0cf; }}
    .sample.dashed {{ border-top-style: dashed; }}
    .dot {{ width: 9px; height: 9px; border-radius: 50%; background: #8f98aa; }}
    .link {{
      stroke: var(--line);
      stroke-opacity: 0.42;
      stroke-width: 1.2;
      marker-end: url(#arrow);
    }}
    .link.deep {{ stroke: #d9dde8; stroke-opacity: 0.66; stroke-width: 1.7; }}
    .link.adjacent {{ stroke-dasharray: 6 5; }}
    .link.candidate {{ stroke-opacity: 0.25; }}
    .link.explored {{ stroke: var(--explored); stroke-width: 2.6; stroke-opacity: 0.9; }}
    .node circle {{
      stroke: rgba(255,255,255,0.56);
      stroke-width: 1.2;
      cursor: grab;
    }}
    .node.candidate circle {{
      stroke-dasharray: 3 3;
      stroke-opacity: 0.55;
    }}
    .node.explored circle {{
      stroke: var(--explored);
      stroke-width: 3;
    }}
    .node text {{
      fill: var(--text);
      paint-order: stroke;
      stroke: rgba(17,19,24,0.92);
      stroke-width: 4px;
      font-size: 11px;
      pointer-events: none;
    }}
    .node.dim, .link.dim {{ opacity: 0.08; }}
    .tooltip {{
      position: fixed;
      z-index: 5;
      pointer-events: none;
      max-width: 320px;
      padding: 8px 10px;
      background: rgba(10, 12, 16, 0.94);
      border: 1px solid rgba(255,255,255,0.14);
      border-radius: 6px;
      color: var(--text);
      font-size: 12px;
      line-height: 1.35;
      opacity: 0;
      transform: translate(10px, 10px);
    }}
  </style>
</head>
<body>
  <section class="toolbar">
    <h1>Wikis Supabase Graph</h1>
    <div class="meta" id="meta"></div>
    <div class="controls">
      <input id="search" type="search" placeholder="Find a topic">
      <button id="reset">Reset View</button>
      <label><input id="toggleCandidates" type="checkbox" checked> Candidates</label>
    </div>
    <div class="legend">
      <span><i class="sample"></i> Deepening / prerequisite</span>
      <span><i class="sample dashed"></i> Adjacent / neighbor</span>
      <span><i class="dot"></i> Pending candidate</span>
      <span><i class="dot" style="background: var(--explored)"></i> Explored path</span>
    </div>
  </section>
  <svg id="graph" role="img" aria-label="Wikis graph visualization"></svg>
  <div class="tooltip" id="tooltip"></div>
  <script>
    const graph = {graph_json};
    const pillarColors = {colors_json};
    const svg = document.getElementById("graph");
    const tooltip = document.getElementById("tooltip");
    const search = document.getElementById("search");
    const toggleCandidates = document.getElementById("toggleCandidates");
    const reset = document.getElementById("reset");
    const meta = document.getElementById("meta");
    const width = window.innerWidth;
    const height = window.innerHeight;
    svg.setAttribute("viewBox", `0 0 ${{width}} ${{height}}`);
    meta.textContent = `${{graph.stats.nodes}} nodes, ${{graph.stats.renderedEdges}} routes, ${{graph.stats.exploredEvents}} explored events`;

    const pillarBuckets = new Map();
    for (const node of graph.nodes) {{
      const key = node.pillar || "candidate";
      if (!pillarBuckets.has(key)) pillarBuckets.set(key, []);
      pillarBuckets.get(key).push(node);
    }}
    const pillarOrder = Array.from(pillarBuckets.keys()).sort((a, b) => a.localeCompare(b));
    const initialPosition = (node, index) => {{
      const pillarIndex = Math.max(0, pillarOrder.indexOf(node.pillar || "candidate"));
      const bucket = pillarBuckets.get(node.pillar || "candidate") || [];
      const localIndex = bucket.findIndex(item => item.id === node.id);
      const globalRadius = Math.min(width, height) * 0.34;
      const localRadius = 42 + Math.sqrt(Math.max(localIndex, 0)) * 34;
      const clusterAngle = (pillarIndex / Math.max(1, pillarOrder.length)) * Math.PI * 2 - Math.PI / 2;
      const localAngle = localIndex * 2.399963229728653;
      return {{
        x: width / 2 + Math.cos(clusterAngle) * globalRadius + Math.cos(localAngle) * localRadius,
        y: height / 2 + Math.sin(clusterAngle) * globalRadius * 0.72 + Math.sin(localAngle) * localRadius
      }};
    }};
    const nodes = graph.nodes.map((node, index) => {{
      const position = initialPosition(node, index);
      return {{
      ...node,
      x: position.x,
      y: position.y,
      vx: 0,
      vy: 0
      }};
    }});
    const byId = new Map(nodes.map(node => [node.id, node]));
    const edges = graph.edges
      .filter(edge => byId.has(edge.source) && byId.has(edge.target))
      .map(edge => ({{ ...edge, sourceNode: byId.get(edge.source), targetNode: byId.get(edge.target) }}));
    const exploredEdges = graph.exploredEdges
      .filter(edge => byId.has(edge.source) && byId.has(edge.target))
      .map(edge => ({{ ...edge, sourceNode: byId.get(edge.source), targetNode: byId.get(edge.target) }}));

    svg.innerHTML = `
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="12" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#8d96a8"></path>
        </marker>
      </defs>
      <g id="viewport">
        <g id="links"></g>
        <g id="exploredLinks"></g>
        <g id="nodes"></g>
      </g>
    `;
    const viewport = svg.querySelector("#viewport");
    const linkLayer = svg.querySelector("#links");
    const exploredLayer = svg.querySelector("#exploredLinks");
    const nodeLayer = svg.querySelector("#nodes");

    const linkEls = edges.map(edge => {{
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.classList.add("link", edge.lineStyle === "solid" ? "deep" : "adjacent", edge.kind);
      line.dataset.source = edge.source;
      line.dataset.target = edge.target;
      line.dataset.kind = edge.kind;
      line.dataset.title = `${{edge.source}} → ${{edge.target}} (${{edge.type}})`;
      linkLayer.appendChild(line);
      return line;
    }});
    const exploredEls = exploredEdges.map(edge => {{
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.classList.add("link", "explored");
      exploredLayer.appendChild(line);
      return line;
    }});
    const nodeEls = nodes.map(node => {{
      const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
      group.classList.add("node", node.kind);
      if (node.explored) group.classList.add("explored");
      group.dataset.id = node.id;
      group.dataset.title = node.title.toLowerCase();
      const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circle.setAttribute("r", node.kind === "candidate" ? "5.5" : "8");
      circle.setAttribute("fill", pillarColors[node.pillar] || pillarColors.candidate);
      const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
      text.setAttribute("x", "11");
      text.setAttribute("y", "4");
      text.textContent = node.title;
      group.appendChild(circle);
      group.appendChild(text);
      group.addEventListener("pointerdown", event => startDrag(event, node));
      group.addEventListener("pointerenter", event => showTooltip(event, node));
      group.addEventListener("pointermove", moveTooltip);
      group.addEventListener("pointerleave", hideTooltip);
      nodeLayer.appendChild(group);
      return group;
    }});

    let dragged = null;
    let transform = {{ x: 0, y: 0, scale: 1 }};
    let panStart = null;

    svg.addEventListener("wheel", event => {{
      event.preventDefault();
      const delta = event.deltaY > 0 ? 0.92 : 1.08;
      transform.scale = Math.min(4, Math.max(0.25, transform.scale * delta));
      applyTransform();
    }}, {{ passive: false }});
    svg.addEventListener("pointerdown", event => {{
      if (event.target.closest(".node")) return;
      panStart = {{ x: event.clientX, y: event.clientY, tx: transform.x, ty: transform.y }};
      svg.setPointerCapture(event.pointerId);
    }});
    svg.addEventListener("pointermove", event => {{
      if (!panStart || dragged) return;
      transform.x = panStart.tx + event.clientX - panStart.x;
      transform.y = panStart.ty + event.clientY - panStart.y;
      applyTransform();
    }});
    svg.addEventListener("pointerup", () => {{ panStart = null; dragged = null; }});
    reset.addEventListener("click", () => {{
      transform = {{ x: 0, y: 0, scale: 1 }};
      search.value = "";
      applyFilter();
      applyTransform();
    }});
    search.addEventListener("input", applyFilter);
    toggleCandidates.addEventListener("change", applyFilter);

    function startDrag(event, node) {{
      dragged = node;
      node.fx = node.x;
      node.fy = node.y;
      event.currentTarget.setPointerCapture(event.pointerId);
      event.currentTarget.addEventListener("pointermove", dragMove);
      event.currentTarget.addEventListener("pointerup", dragEnd, {{ once: true }});
    }}
    function dragMove(event) {{
      if (!dragged) return;
      dragged.x = (event.clientX - transform.x) / transform.scale;
      dragged.y = (event.clientY - transform.y) / transform.scale;
      dragged.vx = 0;
      dragged.vy = 0;
      render();
    }}
    function dragEnd(event) {{
      event.currentTarget.removeEventListener("pointermove", dragMove);
      dragged = null;
    }}
    function applyTransform() {{
      viewport.setAttribute("transform", `translate(${{transform.x}} ${{transform.y}}) scale(${{transform.scale}})`);
    }}
    function showTooltip(event, node) {{
      tooltip.innerHTML = `<strong>${{node.title}}</strong><br>${{node.kind}} · ${{node.pillar}}<br>${{node.qualityStatus}} / ${{node.generationStatus}}`;
      tooltip.style.opacity = 1;
      moveTooltip(event);
    }}
    function moveTooltip(event) {{
      tooltip.style.left = `${{event.clientX}}px`;
      tooltip.style.top = `${{event.clientY}}px`;
    }}
    function hideTooltip() {{
      tooltip.style.opacity = 0;
    }}
    function applyFilter() {{
      const query = search.value.trim().toLowerCase();
      const showCandidates = toggleCandidates.checked;
      nodeEls.forEach(el => {{
        const node = byId.get(el.dataset.id);
        const hiddenCandidate = !showCandidates && node.kind === "candidate";
        const missesSearch = query && !el.dataset.title.includes(query) && !el.dataset.id.includes(query);
        el.classList.toggle("dim", hiddenCandidate || missesSearch);
      }});
      linkEls.forEach(el => {{
        const source = byId.get(el.dataset.source);
        const target = byId.get(el.dataset.target);
        const hiddenCandidate = !showCandidates && (el.dataset.kind === "candidate" || source.kind === "candidate" || target.kind === "candidate");
        const missesSearch = query && !source.title.toLowerCase().includes(query) && !target.title.toLowerCase().includes(query);
        el.classList.toggle("dim", hiddenCandidate || missesSearch);
      }});
    }}
    function tick() {{
      for (const node of nodes) {{
        const pillarIndex = Object.keys(pillarColors).indexOf(node.pillar);
        const angle = (pillarIndex >= 0 ? pillarIndex : 0) / 5 * Math.PI * 2;
        const anchorX = width / 2 + Math.cos(angle) * width * 0.34;
        const anchorY = height / 2 + Math.sin(angle) * height * 0.28;
        node.vx += (anchorX - node.x) * 0.00045;
        node.vy += (anchorY - node.y) * 0.00045;
      }}
      for (const edge of edges) {{
        const source = edge.sourceNode;
        const target = edge.targetNode;
        const dx = target.x - source.x;
        const dy = target.y - source.y;
        const distance = Math.max(1, Math.hypot(dx, dy));
        const desired = edge.lineStyle === "solid" ? 210 : 270;
        const force = (distance - desired) * 0.00055 * Math.max(0.20, edge.strength);
        const fx = dx / distance * force;
        const fy = dy / distance * force;
        source.vx += fx;
        source.vy += fy;
        target.vx -= fx;
        target.vy -= fy;
      }}
      for (let i = 0; i < nodes.length; i++) {{
        for (let j = i + 1; j < nodes.length; j++) {{
          const a = nodes[i];
          const b = nodes[j];
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const distance = Math.max(1, Math.hypot(dx, dy));
          if (distance > 360) continue;
          const force = 95 / (distance * distance);
          const fx = dx / distance * force;
          const fy = dy / distance * force;
          a.vx -= fx;
          a.vy -= fy;
          b.vx += fx;
          b.vy += fy;
        }}
      }}
      for (const node of nodes) {{
        if (node === dragged) continue;
        node.vx *= 0.91;
        node.vy *= 0.91;
        node.x = Math.min(width * 1.7, Math.max(-width * 0.7, node.x + node.vx));
        node.y = Math.min(height * 1.7, Math.max(-height * 0.7, node.y + node.vy));
      }}
      render();
      requestAnimationFrame(tick);
    }}
    function render() {{
      linkEls.forEach((line, index) => {{
        const edge = edges[index];
        line.setAttribute("x1", edge.sourceNode.x);
        line.setAttribute("y1", edge.sourceNode.y);
        line.setAttribute("x2", edge.targetNode.x);
        line.setAttribute("y2", edge.targetNode.y);
      }});
      exploredEls.forEach((line, index) => {{
        const edge = exploredEdges[index];
        line.setAttribute("x1", edge.sourceNode.x);
        line.setAttribute("y1", edge.sourceNode.y);
        line.setAttribute("x2", edge.targetNode.x);
        line.setAttribute("y2", edge.targetNode.y);
      }});
      nodeEls.forEach((group, index) => {{
        const node = nodes[index];
        group.setAttribute("transform", `translate(${{node.x}} ${{node.y}})`);
      }});
    }}
    applyFilter();
    tick();
  </script>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export an interactive Wikis graph visualization from Supabase.")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--out", type=Path, default=Path("data/graph/supabase_graph.html"))
    parser.add_argument("--json-out", type=Path, help="Optional JSON export path for graph data.")
    parser.add_argument("--session-id", help="Highlight one recorded session_id from exploration_events.")
    parser.add_argument("--anonymous-session-id", help="Highlight one anonymous_session_id from exploration_events.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(args.env_file)
    database_url = args.database_url or os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: --database-url or DATABASE_URL is required", file=sys.stderr)
        return 2

    graph = fetch_graph(database_url, args.session_id, args.anonymous_session_id)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html_document(graph), encoding="utf-8")
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(graph, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    print(json.dumps(graph["stats"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
