from __future__ import annotations

import json
import uuid


NAMESPACE = uuid.UUID("73fffd0f-a939-5cde-a1b5-6f95fda56f10")


def stable_uuid(*parts: object) -> str:
    return str(uuid.uuid5(NAMESPACE, ":".join(str(part) for part in parts)))


def sql_literal(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def jsonb_literal(value: object) -> str:
    return f"{sql_literal(json.dumps(value, ensure_ascii=False, sort_keys=True))}::jsonb"


def timestamptz_literal(value: object) -> str:
    return f"{sql_literal(value)}::timestamptz" if value else "null"


def uuid_literal(value: str | None) -> str:
    return f"{sql_literal(value)}::uuid" if value else "null"


def statement(lines: list[str]) -> str:
    return "\n".join(lines) + "\n"


def asset_insert(
    *,
    asset_id: str,
    topic_id: str | None,
    pillar: str | None,
    image_candidate_id: str | None,
    asset_type: str,
    url: str | None,
    thumbnail_url: str | None,
    attribution: str | None,
    license_name: str | None,
    quality_score: object,
) -> str:
    return statement(
        [
            "insert into topic_assets (",
            "  id, topic_id, pillar, image_candidate_id, asset_type, url, thumbnail_url,",
            "  attribution, license, quality_score, approved",
            ") values (",
            f"  {uuid_literal(asset_id)},",
            f"  {sql_literal(topic_id)},",
            f"  {sql_literal(pillar)},",
            f"  {uuid_literal(image_candidate_id)},",
            f"  {sql_literal(asset_type)},",
            f"  {sql_literal(url)},",
            f"  {sql_literal(thumbnail_url)},",
            f"  {sql_literal(attribution)},",
            f"  {sql_literal(license_name)},",
            f"  {sql_literal(quality_score)},",
            "  true",
            ") on conflict (id) do update set",
            "  topic_id = excluded.topic_id,",
            "  pillar = excluded.pillar,",
            "  image_candidate_id = excluded.image_candidate_id,",
            "  asset_type = excluded.asset_type,",
            "  url = excluded.url,",
            "  thumbnail_url = excluded.thumbnail_url,",
            "  attribution = excluded.attribution,",
            "  license = excluded.license,",
            "  quality_score = excluded.quality_score,",
            "  approved = excluded.approved;",
        ]
    )
