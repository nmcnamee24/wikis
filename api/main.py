from __future__ import annotations

import os
import sys
import threading
import time
from argparse import Namespace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import psycopg


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from feed_next import load_graph_from_database, resolve_next_from_database  # noqa: E402
from generate_node_cards import DEFAULT_LOCK_TTL_MINUTES, LOCK_OWNER, load_targets, process_targets  # noqa: E402
from wiki_to_card import DEFAULT_OPENAI_MODEL  # noqa: E402


app = FastAPI(title="Wikis API", version="0.1.0")
_generator_stop = threading.Event()
_generator_thread: threading.Thread | None = None
_generator_status: dict[str, Any] = {
    "enabled": False,
    "running": False,
    "lastCheckedAt": None,
    "lastSummary": None,
    "lastError": None,
}


class FeedNextRequest(BaseModel):
    currentTopicId: str
    gesture: str = Field(pattern="^(down|right|left)$")
    exploredTopicIds: list[str] = Field(default_factory=list)
    savedTopicIds: list[str] = Field(default_factory=list)
    allowPrototypeContent: bool = True


class ExplorationEventRequest(BaseModel):
    sessionId: str
    anonymousSessionId: str | None = None
    userId: UUID | None = None
    fromTopicId: str | None = None
    toTopicId: str | None = None
    gesture: str = Field(pattern="^(start|down|right|left|back|save|unsave)$")
    reasonCode: str | None = None
    dwellMs: int | None = Field(default=None, ge=0)
    saved: bool = False
    clientEventAt: str | None = None


class SaveTopicRequest(BaseModel):
    userId: UUID
    topicId: str
    sourceEventId: UUID | None = None


def database_url() -> str:
    value = os.environ.get("DATABASE_URL")
    if not value:
        raise HTTPException(status_code=503, detail="DATABASE_URL is not configured")
    return value


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int | None = None) -> int | None:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return int(value)


def env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return float(value)


def node_generator_args() -> Namespace:
    return Namespace(
        execute=True,
        sql_out=None,
        cards_out=None,
        all=False,
        include_failed=False,
        limit=env_int("WIKIS_NODE_GENERATOR_LIMIT"),
        delay=0.0,
        condenser=os.environ.get("WIKIS_NODE_GENERATOR_CONDENSER", "local"),
        openai_model=os.environ.get("WIKIS_OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
        include_images=env_bool("WIKIS_NODE_GENERATOR_INCLUDE_IMAGES"),
        batch_size=env_int("WIKIS_NODE_GENERATOR_BATCH_SIZE", 50) or 50,
        lock_owner=os.environ.get("WIKIS_INGEST_LOCK_OWNER", LOCK_OWNER),
        lock_ttl_minutes=env_int("WIKIS_NODE_GENERATOR_LOCK_TTL_MINUTES", DEFAULT_LOCK_TTL_MINUTES)
        or DEFAULT_LOCK_TTL_MINUTES,
        mark_failed_on_error=False,
    )


def node_generator_loop() -> None:
    args = node_generator_args()
    poll_interval = env_float("WIKIS_NODE_GENERATOR_POLL_INTERVAL", 15.0)
    url = os.environ.get("DATABASE_URL")
    if not url:
        _generator_status.update({"running": False, "lastError": "DATABASE_URL is not configured"})
        return

    _generator_status.update({"enabled": True, "running": True, "lastError": None})
    while not _generator_stop.is_set():
        try:
            targets = load_targets(
                url,
                all_nodes=False,
                include_failed=False,
                limit=args.limit,
            )
            _generator_status["lastCheckedAt"] = datetime.now(UTC).replace(microsecond=0).isoformat()
            if targets:
                summary = process_targets(args, url, targets, truncate_sql_out=False)
                _generator_status.update({"lastSummary": summary, "lastError": None})
                continue
            _generator_status.update(
                {
                    "lastSummary": {"attempted": 0, "previewed": 0, "execute": True},
                    "lastError": None,
                }
            )
            _generator_stop.wait(poll_interval)
        except Exception as exc:  # noqa: BLE001 - background worker should stay alive.
            _generator_status.update(
                {
                    "lastCheckedAt": datetime.now(UTC).replace(microsecond=0).isoformat(),
                    "lastError": str(exc),
                }
            )
            _generator_stop.wait(poll_interval)
    _generator_status["running"] = False


@app.on_event("startup")
def start_node_generator() -> None:
    global _generator_thread
    enabled = env_bool("WIKIS_ENABLE_NODE_GENERATOR")
    _generator_status["enabled"] = enabled
    if not enabled or (_generator_thread and _generator_thread.is_alive()):
        return
    _generator_stop.clear()
    _generator_thread = threading.Thread(target=node_generator_loop, name="wikis-node-generator", daemon=True)
    _generator_thread.start()


@app.on_event("shutdown")
def stop_node_generator() -> None:
    _generator_stop.set()
    if _generator_thread and _generator_thread.is_alive():
        _generator_thread.join(timeout=5)


def execute_one(sql: str, params: tuple[Any, ...]) -> Any:
    try:
        with psycopg.connect(database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                row = cursor.fetchone()
                connection.commit()
                return row[0] if row else None
    except Exception as exc:  # noqa: BLE001 - API should return bounded DB errors.
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "name": "Wikis API",
        "status": "ok",
        "endpoints": [
            "/health",
            "/v1/feed/next",
            "/v1/topics/{topic_id}",
            "/v1/events",
            "/v1/saved-topics",
            "/v1/generator/status",
        ],
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/generator/status")
def generator_status() -> dict[str, Any]:
    return dict(_generator_status)


@app.post("/v1/feed/next")
def feed_next(request: FeedNextRequest) -> dict[str, Any]:
    try:
        return resolve_next_from_database(database_url(), request.model_dump())
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - keep API errors bounded.
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/v1/topics/{topic_id}")
def get_topic(topic_id: str) -> dict[str, Any]:
    try:
        graph = load_graph_from_database(database_url())
        for topic in graph.get("topics", []):
            if topic.get("id") == topic_id:
                return topic
        raise HTTPException(status_code=404, detail="topic is not generated yet")
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - keep API errors bounded.
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/v1/events")
def record_event(request: ExplorationEventRequest) -> dict[str, Any]:
    if request.userId is None and request.anonymousSessionId is None:
        raise HTTPException(status_code=422, detail="userId or anonymousSessionId is required")
    event_id = execute_one(
        """
        insert into exploration_events (
          user_id, anonymous_session_id, session_id, from_topic_id, to_topic_id,
          gesture, reason_code, dwell_ms, saved, client_event_at
        ) values (
          %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::timestamptz
        )
        returning id::text;
        """,
        (
            str(request.userId) if request.userId else None,
            request.anonymousSessionId,
            request.sessionId,
            request.fromTopicId,
            request.toTopicId,
            request.gesture,
            request.reasonCode,
            request.dwellMs,
            request.saved,
            request.clientEventAt,
        ),
    )
    return {"id": event_id, "status": "recorded"}


@app.post("/v1/saved-topics")
def save_topic(request: SaveTopicRequest) -> dict[str, Any]:
    execute_one(
        """
        insert into saved_topics (user_id, topic_id, source_event_id)
        values (%s, %s, %s)
        on conflict (user_id, topic_id) do update set
          saved_at = now(),
          source_event_id = excluded.source_event_id
        returning topic_id;
        """,
        (str(request.userId), request.topicId, str(request.sourceEventId) if request.sourceEventId else None),
    )
    return {"topicId": request.topicId, "status": "saved"}
