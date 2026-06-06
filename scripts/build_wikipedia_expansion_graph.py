#!/usr/bin/env python3
"""Build a visual-first Wikipedia expansion graph.

This intentionally does not generate Wikis card content. It creates visible
nodes from Wikipedia page titles first, stores the graph, and leaves content
backfill as a separate step.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import random
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from collections import deque
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


API_URL = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "WikisPrototype/0.1 (visual exploration prototype)"
DEEP_EDGE_TYPES = {"deeper", "prerequisite"}


def slugify(value: str) -> str:
    value = value.lower().replace("&", " and ")
    value = re.sub(r"\([^)]*\)", "", value)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "topic"


class FirstParagraphLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.paragraph_depth = 0
        self.in_first_paragraph = False
        self.finished_first_paragraph = False
        self.current_href: str | None = None
        self.current_label: list[str] = []
        self.links: list[dict[str, str]] = []
        self.seen_titles: set[str] = set()
        self._paragraph_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_by_name = {name: value for name, value in attrs}
        if tag == "p" and not self.finished_first_paragraph:
            self.paragraph_depth += 1
            if not self.in_first_paragraph:
                self.in_first_paragraph = True
                self._paragraph_text = []
            return

        if tag == "a" and self.in_first_paragraph:
            href = attrs_by_name.get("href") or ""
            title = attrs_by_name.get("title") or ""
            normalized = normalize_wiki_href(href, title)
            if normalized:
                self.current_href = normalized
                self.current_label = []

    def handle_data(self, data: str) -> None:
        if self.in_first_paragraph:
            self._paragraph_text.append(data)
        if self.current_href:
            self.current_label.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.current_href:
            title = self.current_href
            if title not in self.seen_titles:
                label = " ".join("".join(self.current_label).split()) or title
                self.links.append({"title": title, "label": label})
                self.seen_titles.add(title)
            self.current_href = None
            self.current_label = []
            return

        if tag == "p" and self.in_first_paragraph:
            self.paragraph_depth = max(0, self.paragraph_depth - 1)
            text = " ".join("".join(self._paragraph_text).split())
            if text:
                self.finished_first_paragraph = True
                self.in_first_paragraph = False


def normalize_wiki_href(href: str, title: str) -> str | None:
    if not href.startswith("/wiki/"):
        return None
    raw = urllib.parse.unquote(href.removeprefix("/wiki/")).split("#", 1)[0]
    if not raw or ":" in raw:
        return None
    normalized = raw.replace("_", " ").strip()
    if not normalized:
        return None
    return title.strip() or normalized


def get_json(params: dict[str, Any], timeout: int = 20) -> dict[str, Any]:
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == 2:
                raise
            retry_after = exc.headers.get("Retry-After")
            delay = float(retry_after) if retry_after and retry_after.isdigit() else 3.0 * (attempt + 1)
            time.sleep(delay)
    raise RuntimeError("unreachable Wikipedia request retry state")


def random_article_title() -> str:
    data = get_json(
        {
            "action": "query",
            "format": "json",
            "list": "random",
            "rnnamespace": 0,
            "rnlimit": 1,
        }
    )
    return data["query"]["random"][0]["title"]


def fetch_lead_links(title: str, limit: int) -> tuple[str, int | None, list[dict[str, str]]]:
    data = get_json(
        {
            "action": "parse",
            "format": "json",
            "page": title,
            "prop": "text",
            "section": 0,
            "redirects": 1,
        }
    )
    parsed = data.get("parse", {})
    canonical_title = parsed.get("title") or title
    page_id = parsed.get("pageid")
    raw_html = parsed.get("text", {}).get("*", "")
    parser = FirstParagraphLinkParser()
    parser.feed(raw_html)
    return canonical_title, page_id, parser.links[:limit]


@dataclass(frozen=True)
class FrontierItem:
    title: str
    depth: int
    parent_id: str | None


def classify_edge(index: int, sibling_count: int) -> str:
    split = max(1, math.ceil(sibling_count / 2))
    return "deeper" if index < split else "neighbor"


def build_graph(args: argparse.Namespace) -> dict[str, Any]:
    seed_title = args.seed_title or random_article_title()
    frontier: deque[FrontierItem] = deque([FrontierItem(seed_title, 0, None)])
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}
    expanded_ids: set[str] = set()
    queued_ids: set[str] = {slugify(seed_title)}
    failures: list[dict[str, str]] = []

    while frontier and len(nodes) < args.max_nodes:
        item = frontier.popleft()
        requested_id = slugify(item.title)
        existing = nodes.get(requested_id)
        if existing and existing["depth"] < item.depth:
            continue
        if item.depth > args.max_depth:
            continue

        try:
            canonical_title, page_id, links = fetch_lead_links(item.title, args.links_per_topic)
            node_id = slugify(canonical_title)
            node = nodes.setdefault(
                node_id,
                {
                    "id": node_id,
                    "title": canonical_title,
                    "depth": item.depth,
                    "status": "expanded",
                    "pageId": page_id,
                    "contentStatus": "missing",
                    "source": "wikipedia_parse_lead",
                },
            )
            node["depth"] = min(node["depth"], item.depth)
            node["pageId"] = page_id
            node["status"] = "expanded"
            expanded_ids.add(node_id)

            print(f"{canonical_title} depth={item.depth} links={len(links)}")
            sibling_count = len(links)
            for index, link in enumerate(links):
                child_title = link["title"]
                child_id = slugify(child_title)
                if len(nodes) >= args.max_nodes and child_id not in nodes:
                    break
                nodes.setdefault(
                    child_id,
                    {
                        "id": child_id,
                        "title": child_title,
                        "depth": item.depth + 1,
                        "status": "placeholder",
                        "pageId": None,
                        "contentStatus": "missing",
                        "source": "wikipedia_first_paragraph_link",
                    },
                )
                nodes[child_id]["depth"] = min(nodes[child_id]["depth"], item.depth + 1)
                edge_type = classify_edge(index, sibling_count)
                edge_id = f"{node_id}__{edge_type}__{child_id}"
                edges.setdefault(
                    edge_id,
                    {
                        "id": edge_id,
                        "from": node_id,
                        "to": child_id,
                        "type": edge_type,
                        "rank": index,
                        "label": link.get("label") or child_title,
                        "source": "wikipedia_first_paragraph_link",
                    },
                )
                if item.depth + 1 <= args.max_depth and child_id not in expanded_ids and child_id not in queued_ids:
                    frontier.append(FrontierItem(child_title, item.depth + 1, node_id))
                    queued_ids.add(child_id)
        except Exception as exc:  # noqa: BLE001 - batch crawl should keep going.
            failures.append({"title": item.title, "error": str(exc)})
            node = nodes.setdefault(
                requested_id,
                {
                    "id": requested_id,
                    "title": item.title,
                    "depth": item.depth,
                    "status": "failed",
                    "pageId": None,
                    "contentStatus": "missing",
                    "source": "wikipedia_parse_lead",
                },
            )
            node["status"] = "failed"
            print(f"ERROR: {item.title}: {exc}", file=sys.stderr)

        if frontier and args.delay > 0:
            time.sleep(args.delay)

    node_list = sorted(nodes.values(), key=lambda node: (node["depth"], node["title"]))
    edge_list = sorted(edges.values(), key=lambda edge: (edge["from"], edge["rank"], edge["to"]))
    return {
        "schemaVersion": 1,
        "graphId": args.graph_id,
        "seedTitle": seed_title,
        "maxDepth": args.max_depth,
        "linksPerTopic": args.links_per_topic,
        "nodes": node_list,
        "edges": edge_list,
        "stats": {
            "nodeCount": len(node_list),
            "edgeCount": len(edge_list),
            "expandedCount": len(expanded_ids),
            "placeholderCount": sum(1 for node in node_list if node["status"] == "placeholder"),
            "failureCount": len(failures),
        },
        "failures": failures,
    }


def html_document(graph: dict[str, Any]) -> str:
    graph_json = json.dumps(graph, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Wikis Wikipedia Expansion Graph</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0f1115;
      --panel: rgba(18, 21, 27, 0.92);
      --text: #f4f0e8;
      --muted: #aab2c3;
      --deep: #e7e0c4;
      --neighbor: #6fc4ff;
      --placeholder: #8b93a5;
      --expanded: #72d69c;
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
      z-index: 4;
      top: 14px;
      left: 14px;
      width: min(430px, calc(100vw - 28px));
      padding: 12px;
      background: var(--panel);
      border: 1px solid rgba(255,255,255,0.13);
      border-radius: 8px;
      box-shadow: 0 18px 48px rgba(0,0,0,0.28);
    }}
    h1 {{ margin: 0 0 7px; font-size: 16px; letter-spacing: 0; }}
    .meta {{ color: var(--muted); font-size: 12px; line-height: 1.35; }}
    .controls {{ display: flex; gap: 8px; margin-top: 10px; }}
    button, input {{
      font: inherit;
      font-size: 13px;
      border-radius: 6px;
      border: 1px solid rgba(255,255,255,0.16);
      color: var(--text);
      background: rgba(255,255,255,0.07);
      padding: 8px 10px;
    }}
    input {{ min-width: 0; flex: 1; }}
    button {{ cursor: pointer; }}
    .link {{
      stroke-width: 1.35;
      stroke-opacity: 0.58;
      marker-end: url(#arrow);
    }}
    .link.deeper {{ stroke: var(--deep); }}
    .link.neighbor {{ stroke: var(--neighbor); stroke-dasharray: 7 6; stroke-opacity: 0.48; }}
    .node circle {{
      stroke: rgba(255,255,255,0.58);
      stroke-width: 1.1;
      cursor: grab;
    }}
    .node.placeholder circle {{ fill: var(--placeholder); stroke-dasharray: 3 3; }}
    .node.expanded circle {{ fill: var(--expanded); }}
    .node.failed circle {{ fill: #e36d6d; }}
    .node text {{
      fill: var(--text);
      paint-order: stroke;
      stroke: rgba(15,17,21,0.96);
      stroke-width: 4px;
      font-size: 11px;
      pointer-events: none;
    }}
    .dim {{ opacity: 0.12; }}
  </style>
</head>
<body>
  <section class="toolbar">
    <h1>Wikipedia Expansion Graph</h1>
    <div class="meta" id="meta"></div>
    <div class="controls">
      <input id="search" type="search" placeholder="Find a node">
      <button id="reset" type="button">Reset View</button>
    </div>
  </section>
  <svg id="graph" role="img" aria-label="Procedural Wikipedia graph"></svg>
  <script>
    const graph = {graph_json};
    const svg = document.getElementById("graph");
    const search = document.getElementById("search");
    const reset = document.getElementById("reset");
    const meta = document.getElementById("meta");
    const width = window.innerWidth;
    const height = window.innerHeight;
    svg.setAttribute("viewBox", `0 0 ${{width}} ${{height}}`);
    meta.textContent = `${{graph.seedTitle}} · depth ${{graph.maxDepth}} · ${{graph.stats.nodeCount}} nodes · ${{graph.stats.edgeCount}} real lead-link routes · ${{graph.stats.placeholderCount}} placeholders`;

    const maxDepth = Math.max(...graph.nodes.map(node => node.depth), 1);
    const nodesByDepth = new Map();
    for (const node of graph.nodes) {{
      if (!nodesByDepth.has(node.depth)) nodesByDepth.set(node.depth, []);
      nodesByDepth.get(node.depth).push(node);
    }}
    const nodes = graph.nodes.map(node => {{
      const ring = nodesByDepth.get(node.depth) || [];
      const localIndex = ring.findIndex(item => item.id === node.id);
      const count = Math.max(1, ring.length);
      const depthRatio = node.depth / Math.max(1, maxDepth);
      const radius = node.depth === 0 ? 0 : Math.min(width, height) * (0.16 + depthRatio * 0.54);
      const angle = (localIndex / count) * Math.PI * 2 + node.depth * 0.67;
      return {{
        ...node,
        x: width / 2 + Math.cos(angle) * radius,
        y: height / 2 + Math.sin(angle) * radius * 0.76,
        vx: 0,
        vy: 0
      }};
    }});
    const byId = new Map(nodes.map(node => [node.id, node]));
    const edges = graph.edges
      .filter(edge => byId.has(edge.from) && byId.has(edge.to))
      .map(edge => ({{ ...edge, sourceNode: byId.get(edge.from), targetNode: byId.get(edge.to) }}));

    svg.innerHTML = `
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="12" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#9fa8ba"></path>
        </marker>
      </defs>
      <g id="viewport">
        <g id="links"></g>
        <g id="nodes"></g>
      </g>
    `;
    const viewport = svg.querySelector("#viewport");
    const linkLayer = svg.querySelector("#links");
    const nodeLayer = svg.querySelector("#nodes");

    const linkEls = edges.map(edge => {{
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.classList.add("link", edge.type);
      line.dataset.source = edge.from;
      line.dataset.target = edge.to;
      linkLayer.appendChild(line);
      return line;
    }});
    const nodeEls = nodes.map(node => {{
      const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
      group.classList.add("node", node.status);
      group.dataset.id = node.id;
      group.dataset.title = node.title.toLowerCase();
      const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circle.setAttribute("r", node.depth === 0 ? 11 : node.status === "placeholder" ? 5.8 : 7.5);
      const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
      text.setAttribute("x", "11");
      text.setAttribute("y", "4");
      text.textContent = node.title;
      group.appendChild(circle);
      group.appendChild(text);
      group.addEventListener("pointerdown", event => startDrag(event, node));
      nodeLayer.appendChild(group);
      return group;
    }});

    let dragged = null;
    let transform = {{ x: 0, y: 0, scale: 1 }};
    let panStart = null;
    svg.addEventListener("wheel", event => {{
      event.preventDefault();
      const delta = event.deltaY > 0 ? 0.92 : 1.08;
      transform.scale = Math.min(4, Math.max(0.2, transform.scale * delta));
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

    function startDrag(event, node) {{
      dragged = node;
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
    function applyFilter() {{
      const query = search.value.trim().toLowerCase();
      nodeEls.forEach(el => {{
        const misses = query && !el.dataset.title.includes(query) && !el.dataset.id.includes(query);
        el.classList.toggle("dim", misses);
      }});
      linkEls.forEach(el => {{
        const source = byId.get(el.dataset.source);
        const target = byId.get(el.dataset.target);
        const misses = query && !source.title.toLowerCase().includes(query) && !target.title.toLowerCase().includes(query);
        el.classList.toggle("dim", misses);
      }});
    }}
    function tick() {{
      for (const edge of edges) {{
        const source = edge.sourceNode;
        const target = edge.targetNode;
        const dx = target.x - source.x;
        const dy = target.y - source.y;
        const distance = Math.max(1, Math.hypot(dx, dy));
        const desired = edge.type === "deeper" ? 250 : 330;
        const force = (distance - desired) * 0.00016;
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
          if (distance > 520) continue;
          const force = 270 / (distance * distance);
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
        const depthRatio = node.depth / Math.max(1, maxDepth);
        const radius = node.depth === 0 ? 0 : Math.min(width, height) * (0.16 + depthRatio * 0.54);
        const ring = nodesByDepth.get(node.depth) || [];
        const localIndex = ring.findIndex(item => item.id === node.id);
        const angle = (localIndex / Math.max(1, ring.length)) * Math.PI * 2 + node.depth * 0.67;
        const anchorX = width / 2 + Math.cos(angle) * radius;
        const anchorY = height / 2 + Math.sin(angle) * radius * 0.76;
        node.vx += (anchorX - node.x) * 0.00022;
        node.vy += (anchorY - node.y) * 0.00022;
        node.vx *= 0.91;
        node.vy *= 0.91;
        node.x = Math.min(width * 2.0, Math.max(-width, node.x + node.vx));
        node.y = Math.min(height * 2.0, Math.max(-height, node.y + node.vy));
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
      nodeEls.forEach((group, index) => {{
        const node = nodes[index];
        group.setAttribute("transform", `translate(${{node.x}} ${{node.y}})`);
      }});
    }}
    applyFilter();
    applyTransform();
    tick();
  </script>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a visual-first Wikipedia expansion graph.")
    parser.add_argument("seed_title", nargs="?", help="Starting Wikipedia title. Omit with --random.")
    parser.add_argument("--random", action="store_true", help="Start from a random Wikipedia article.")
    parser.add_argument("--max-depth", type=int, default=2)
    parser.add_argument("--links-per-topic", type=int, default=8)
    parser.add_argument("--max-nodes", type=int, default=160)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--graph-id", default="wikis-wikipedia-expansion-v0")
    parser.add_argument("--out", type=Path, default=Path("data/graph/wikipedia_expansion_graph.json"))
    parser.add_argument("--html-out", type=Path, default=Path("data/graph/wikipedia_expansion_graph.html"))
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.random:
        args.seed_title = None
    elif not args.seed_title:
        raise ValueError("Provide a seed title or pass --random.")
    if args.max_depth < 0:
        raise ValueError("--max-depth must be >= 0")
    if args.links_per_topic < 1:
        raise ValueError("--links-per-topic must be >= 1")
    if args.max_nodes < 1:
        raise ValueError("--max-nodes must be >= 1")


def main() -> int:
    args = parse_args()
    try:
        validate_args(args)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    graph = build_graph(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(graph, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.html_out.parent.mkdir(parents=True, exist_ok=True)
    args.html_out.write_text(html_document(graph), encoding="utf-8")
    print(f"wrote {args.out}")
    print(f"wrote {args.html_out}")
    print(json.dumps(graph["stats"], indent=2))
    return 1 if graph["stats"]["failureCount"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
