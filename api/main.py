from __future__ import annotations

import os
import sys
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


app = FastAPI(title="Wikis API", version="0.1.0")


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
        "endpoints": ["/health", "/v1/feed/next", "/v1/topics/{topic_id}", "/v1/events", "/v1/saved-topics"],
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


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
