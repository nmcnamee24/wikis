from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

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


def database_url() -> str:
    value = os.environ.get("DATABASE_URL")
    if not value:
        raise HTTPException(status_code=503, detail="DATABASE_URL is not configured")
    return value


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/feed/next")
def feed_next(request: FeedNextRequest) -> dict[str, Any]:
    try:
        graph = load_graph_from_database(database_url())
        return resolve_next(graph, request.model_dump())
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - keep API errors bounded.
        raise HTTPException(status_code=500, detail=str(exc)) from exc
