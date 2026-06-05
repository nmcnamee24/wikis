from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field
import psycopg


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from backend_ingest import (  # noqa: E402
    DEFAULT_LOCK_OWNER,
    DEFAULT_LOCK_TTL_MINUTES,
    DEFAULT_OPENAI_MODEL,
    NODE_GENERATION_VERSION,
    ingest_sql,
    job_statement,
    statement,
)
from feed_next import load_graph_from_database, resolve_next  # noqa: E402


app = FastAPI(title="Wikis API", version="0.1.0")


class FeedNextRequest(BaseModel):
    currentTopicId: str
    gesture: str = Field(pattern="^(down|right|left)$")
    exploredTopicIds: list[str] = Field(default_factory=list)
    savedTopicIds: list[str] = Field(default_factory=list)
    frontierLimit: int = Field(default=2, ge=0, le=20)
    prefetchLimit: int = Field(default=3, ge=0, le=20)
    allowPrototypeContent: bool = True
    allowPendingCandidateCards: bool = True
    liveGenerationEnabled: bool = True
    liveGenerationLimit: int = Field(default=1, ge=0, le=5)


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


def live_generation_enabled(request: FeedNextRequest) -> bool:
    if not request.liveGenerationEnabled or request.liveGenerationLimit <= 0:
        return False
    return os.environ.get("WIKIS_LIVE_GENERATION_ENABLED", "1").lower() not in {"0", "false", "no"}


def live_generation_condenser() -> str:
    configured = os.environ.get("WIKIS_LIVE_GENERATION_CONDENSER")
    if configured in {"local", "openai"}:
        return configured
    return "openai" if os.environ.get("OPENAI_API_KEY") else "local"


def claim_background_candidates(candidates: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    if limit <= 0:
        return []

    lock_owner = os.environ.get("WIKIS_INGEST_LOCK_OWNER", DEFAULT_LOCK_OWNER)
    ttl_minutes = int(os.environ.get("WIKIS_INGEST_LOCK_TTL_MINUTES", DEFAULT_LOCK_TTL_MINUTES))
    claimed: list[dict[str, Any]] = []

    with psycopg.connect(database_url()) as connection:
        with connection.cursor() as cursor:
            for candidate in candidates:
                if len(claimed) >= limit:
                    break
                title = str(candidate.get("title") or candidate.get("id") or "").strip()
                if not title:
                    continue
                cursor.execute(
                    """
                    insert into ingestion_jobs (
                      requested_title, normalized_title, source, priority, status, attempts,
                      started_at, finished_at, job_kind, lock_owner, locked_until,
                      frontier_depth, frontier_limit, generation_version
                    ) values (
                      %s, %s, 'background_expansion', %s, 'running', 0,
                      now(), null, 'node', %s, now() + (%s::text || ' minutes')::interval,
                      1, %s, %s
                    )
                    on conflict (requested_title, source) do update set
                      status = 'running',
                      priority = greatest(ingestion_jobs.priority, excluded.priority),
                      started_at = now(),
                      finished_at = null,
                      job_kind = excluded.job_kind,
                      lock_owner = excluded.lock_owner,
                      locked_until = excluded.locked_until,
                      frontier_depth = excluded.frontier_depth,
                      frontier_limit = excluded.frontier_limit,
                      generation_version = excluded.generation_version
                    where ingestion_jobs.status not in ('running', 'succeeded')
                       or ingestion_jobs.locked_until < now()
                    returning requested_title;
                    """,
                    (
                        title,
                        str(candidate.get("id") or title),
                        int(candidate.get("priority") or 100),
                        lock_owner,
                        ttl_minutes,
                        limit,
                        NODE_GENERATION_VERSION,
                    ),
                )
                if cursor.fetchone():
                    claimed.append(candidate)
        connection.commit()
    return claimed


def ingest_background_candidates(candidates: list[dict[str, Any]]) -> None:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        return

    condenser = live_generation_condenser()
    model = os.environ.get("WIKIS_OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    lock_owner = os.environ.get("WIKIS_INGEST_LOCK_OWNER", DEFAULT_LOCK_OWNER)
    cards_out = Path(os.environ.get("WIKIS_LIVE_CARDS_OUT", str(ROOT / "data" / "cards")))
    sql_blocks: list[str] = []

    for candidate in candidates:
        title = str(candidate.get("title") or candidate.get("id") or "").strip()
        if not title:
            continue
        try:
            _, sql = ingest_sql(
                title,
                "background_expansion",
                cards_out,
                condenser,
                model,
                lock_owner,
                int(os.environ.get("WIKIS_INGEST_LOCK_TTL_MINUTES", DEFAULT_LOCK_TTL_MINUTES)),
            )
            sql_blocks.append(sql)
        except Exception as exc:  # noqa: BLE001 - background ingestion should be observable, not fatal.
            sql_blocks.append(
                statement(
                    [
                        "begin;",
                        job_statement(
                            title,
                            "background_expansion",
                            "failed",
                            error=str(exc),
                            generation_version=NODE_GENERATION_VERSION,
                            frontier_depth=1,
                            frontier_limit=len(candidates),
                        ),
                        "commit;",
                    ]
                )
            )

    if sql_blocks:
        try:
            with psycopg.connect(db_url) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("\n".join(sql_blocks))
                connection.commit()
        except Exception as exc:  # noqa: BLE001 - never let live generation break feed serving.
            print(f"live background ingestion failed: {exc}", file=sys.stderr)


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
def feed_next(request: FeedNextRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    try:
        graph = load_graph_from_database(database_url())
        response = resolve_next(graph, request.model_dump())
        background_candidates = response.get("backgroundIngestionTopics", [])
        if live_generation_enabled(request) and background_candidates:
            claimed_candidates = claim_background_candidates(background_candidates, request.liveGenerationLimit)
            if claimed_candidates:
                background_tasks.add_task(ingest_background_candidates, claimed_candidates)
            response["liveGeneration"] = {
                "status": "scheduled" if claimed_candidates else "already_queued",
                "limit": request.liveGenerationLimit,
                "candidateTitles": [candidate.get("title") for candidate in claimed_candidates],
            }
        else:
            response["liveGeneration"] = {"status": "idle", "limit": 0, "candidateTitles": []}
        return response
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
