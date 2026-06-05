#!/usr/bin/env python3
"""Validate Step 01 Wikis card JSON files against acceptance criteria."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def validate_card(path: Path, data: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    source = data.get("source", {})
    card = data.get("card", {})
    image = data.get("image", {})
    mapping = data.get("mapping", {})
    quality = data.get("quality", {})

    if not source.get("pageId"):
        issues.append("missing_page_id")
    if not source.get("revisionId"):
        issues.append("missing_revision_id")

    explanation = card.get("explanation", "")
    hook = card.get("hook", "")
    reading_seconds = card.get("readingSeconds")
    if not explanation:
        issues.append("missing_explanation")
    if not hook:
        issues.append("missing_hook")
    if not isinstance(reading_seconds, int) or not 20 <= reading_seconds <= 35:
        issues.append(f"reading_seconds_out_of_range:{reading_seconds}")

    related = card.get("relatedCandidates") or mapping.get("relatedTopicCandidates") or []
    if len(related) < 3:
        issues.append(f"few_related_candidates:{len(related)}")

    strategy = image.get("strategy")
    if strategy == "wikipedia_image":
        selected = image.get("selected")
        if not selected or not selected.get("url"):
            issues.append("missing_selected_image")
        if selected and selected.get("rejectionReasons"):
            issues.append("selected_image_has_rejection_reasons")
    elif strategy == "pillar_background":
        if not image.get("fallbackPillar") or not image.get("reason"):
            issues.append("missing_fallback_image_reason")
    else:
        issues.append(f"unknown_image_strategy:{strategy}")

    if quality.get("issues"):
        issues.append(f"quality_issues:{','.join(quality['issues'])}")
    if quality.get("status") not in {"prototype_pass", "needs_review"}:
        issues.append(f"unknown_quality_status:{quality.get('status')}")

    if data.get("schemaVersion") != 1:
        issues.append("unexpected_schema_version")
    if not path.stem:
        issues.append("bad_filename")
    return issues


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate generated Wikis card JSON files.")
    parser.add_argument("--cards-dir", type=Path, default=Path("data/cards"))
    parser.add_argument("--min-cards", type=int, default=20)
    parser.add_argument("--require-pillars", nargs="*", default=["science", "literature", "society", "history"])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = sorted(args.cards_dir.glob("*.json"))
    issues: list[str] = []
    pillars: Counter[str] = Counter()
    passing = 0

    if len(paths) < args.min_cards:
        issues.append(f"too_few_cards:{len(paths)}")

    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        pillars[data.get("card", {}).get("pillar", "unknown")] += 1
        card_issues = validate_card(path, data)
        if card_issues:
            issues.extend(f"{path.name}:{issue}" for issue in card_issues)
        else:
            passing += 1

    missing_pillars = [pillar for pillar in args.require_pillars if pillars[pillar] == 0]
    for pillar in missing_pillars:
        issues.append(f"missing_pillar:{pillar}")

    print(f"cards: {len(paths)}")
    print(f"passing: {passing}")
    print(f"pillars: {dict(sorted(pillars.items()))}")
    print(f"issues: {len(issues)}")
    for issue in issues[:80]:
        print(f"- {issue}")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
