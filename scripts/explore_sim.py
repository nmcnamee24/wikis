#!/usr/bin/env python3
"""Drive the live Wikis feed API like a bounded exploration session."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from collections import Counter, deque
from pathlib import Path
from typing import Any


GESTURE_CYCLE = ["right", "down", "right", "left"]


def post_json(url: str, payload: dict[str, Any], timeout: int = 30) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc


def choose_gesture(step: int, current_id: str, recent_failures: Counter[str]) -> str:
    if recent_failures[current_id] >= 2:
        return "left"
    return GESTURE_CYCLE[step % len(GESTURE_CYCLE)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulate a bounded user exploration path.")
    parser.add_argument("--api-url", default="https://wikis-production.up.railway.app")
    parser.add_argument("--seed", default="black-hole")
    parser.add_argument("--steps", type=int, default=24)
    parser.add_argument("--delay", type=float, default=1.5)
    parser.add_argument("--frontier-limit", type=int, default=2)
    parser.add_argument("--live-generation-limit", type=int, default=1)
    parser.add_argument("--out", type=Path, default=Path("data/graph/explore_sim_latest.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    endpoint = f"{args.api_url.rstrip('/')}/v1/feed/next"
    current_id = args.seed
    explored_order: list[str] = [current_id]
    explored_set = {current_id}
    recent = deque([current_id], maxlen=8)
    failures: Counter[str] = Counter()
    transcript: list[dict[str, Any]] = []

    for step in range(args.steps):
        gesture = choose_gesture(step, current_id, failures)
        payload = {
            "currentTopicId": current_id,
            "gesture": gesture,
            "exploredTopicIds": explored_order,
            "savedTopicIds": [],
            "frontierLimit": args.frontier_limit,
            "prefetchLimit": 3,
            "allowPrototypeContent": True,
            "liveGenerationEnabled": True,
            "liveGenerationLimit": args.live_generation_limit,
        }
        response = post_json(endpoint, payload)
        next_id = response.get("nextTopicId")
        if not next_id:
            print(f"{step + 1:02d}. {current_id} {gesture} -> no next topic")
            break

        repeated = next_id in explored_set
        live = response.get("liveGeneration") or {}
        generated_titles = [title for title in live.get("candidateTitles", []) if title]
        background_titles = [
            candidate.get("title")
            for candidate in response.get("backgroundIngestionTopics", [])
            if candidate.get("title")
        ]

        transcript.append(
            {
                "step": step + 1,
                "from": current_id,
                "gesture": gesture,
                "to": next_id,
                "repeated": repeated,
                "reasonCode": response.get("reasonCode"),
                "liveGeneration": live,
                "backgroundIngestionTopics": background_titles,
            }
        )
        print(
            f"{step + 1:02d}. {current_id} --{gesture}--> {next_id}"
            f" reason={response.get('reasonCode')}"
            f" live={live.get('status', 'missing')} {generated_titles}"
        )

        if repeated and next_id in recent:
            failures[current_id] += 1
        else:
            failures[current_id] = 0
            current_id = next_id
            explored_set.add(next_id)
            explored_order.append(next_id)
            recent.append(next_id)

        if args.delay > 0 and step < args.steps - 1:
            time.sleep(args.delay)

    output = {
        "apiUrl": args.api_url,
        "seed": args.seed,
        "stepsRequested": args.steps,
        "uniqueTopics": len(explored_set),
        "exploredTopicIds": explored_order,
        "transcript": transcript,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    print(f"unique topics: {len(explored_set)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
