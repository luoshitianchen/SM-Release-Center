"""SM Release Center —— 发布中心：流水线、发布、部署、环境与回滚。"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, Request, status
from pydantic import BaseModel, Field

from app import base

SERVICE = "sm-release-center"
VERSION = "2.0.0"
NAME = "SM Release Center"
DESCRIPTION = "发布中心：流水线、发布、部署、环境与回滚"
PORT = 8550


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _init() -> None:
    with base.db_ctx() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS pipelines (
                id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, repo TEXT NOT NULL,
                default_branch TEXT NOT NULL DEFAULT 'main', environments TEXT NOT NULL DEFAULT '["staging","prod"]',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS releases (
                id TEXT PRIMARY KEY, pipeline_id TEXT NOT NULL, version TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft', created_by TEXT NOT NULL,
                started_at TEXT, finished_at TEXT, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS deployments (
                id TEXT PRIMARY KEY, release_id TEXT NOT NULL, environment TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending', deployed_by TEXT,
                deployed_at TEXT, created_at TEXT NOT NULL
            );
            """
        )


app = base.create_app(
    service=SERVICE, name=NAME, description=DESCRIPTION, version=VERSION, port=PORT,
    dependencies=["sm-iam", "sm-workflow-approval", "sm-observability"],
    events=["release.created", "release.deployed", "release.rolled_back"],
    overview_fn=lambda _r: {
        "summary": {
            "pipelines": base.get_db().execute("SELECT COUNT(*) FROM pipelines").fetchone()[0],
            "deployments": base.get_db().execute("SELECT COUNT(*) FROM deployments").fetchone()[0],
        }
    },
)
_init()


class PipelineIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    repo: str = Field(min_length=2, max_length=200)
    default_branch: str = Field(default="main", min_length=1, max_length=40)
    environments: list[str] = Field(default_factory=lambda: ["staging", "prod"], min_length=1)


class ReleaseIn(BaseModel):
    pipeline_id: str = Field(min_length=8)
    version: str = Field(min_length=2, max_length=40)
    created_by: str = Field(min_length=1, max_length=80)


class DeployIn(BaseModel):
    environment: str = Field(min_length=2, max_length=40)
    deployed_by: str = Field(min_length=1, max_length=80)


@app.post("/api/release/pipelines", status_code=status.HTTP_201_CREATED)
def create_pipeline(payload: PipelineIn, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    pipeline_id = str(uuid.uuid4())
    with base.db_ctx() as conn:
        try:
            conn.execute("INSERT INTO pipelines VALUES (?,?,?,?,?,?)", (pipeline_id, payload.name, payload.repo, payload.default_branch, json.dumps(payload.environments, ensure_ascii=False), _now()))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status.HTTP_409_CONFLICT, "流水线已存在") from exc
    return {"id": pipeline_id, "name": payload.name}


@app.get("/api/release/pipelines")
def list_pipelines() -> dict[str, Any]:
    with base.db_ctx() as conn:
        rows = conn.execute("SELECT * FROM pipelines ORDER BY created_at DESC").fetchall()
    return {"items": [dict(r) for r in rows], "total": len(rows)}


@app.post("/api/release/releases", status_code=status.HTTP_201_CREATED)
def create_release(payload: ReleaseIn, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    release_id = str(uuid.uuid4())
    with base.db_ctx() as conn:
        pipeline = conn.execute("SELECT * FROM pipelines WHERE id=?", (payload.pipeline_id,)).fetchone()
        if not pipeline:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "流水线不存在")
        dup = conn.execute("SELECT 1 FROM releases WHERE pipeline_id=? AND version=? AND status<>'rolled_back'", (payload.pipeline_id, payload.version)).fetchone()
        if dup:
            raise HTTPException(status.HTTP_409_CONFLICT, "该版本已存在且未被回滚")
        conn.execute("INSERT INTO releases (id, pipeline_id, version, status, created_by, started_at, finished_at, created_at) VALUES (?,?,?,?,?,?,?,?)", (release_id, payload.pipeline_id, payload.version, "draft", payload.created_by, None, None, _now()))
        base.record_audit("release.created", payload.created_by, f"release={release_id} version={payload.version}", getattr(request.state, "request_id", ""), getattr(request.state, "trace_id", ""), SERVICE)
    return {"id": release_id, "version": payload.version, "status": "draft"}


@app.get("/api/release/releases")
def list_releases(pipeline_id: str | None = None) -> dict[str, Any]:
    with base.db_ctx() as conn:
        if pipeline_id:
            rows = conn.execute("SELECT * FROM releases WHERE pipeline_id=? ORDER BY created_at DESC", (pipeline_id,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM releases ORDER BY created_at DESC LIMIT 200").fetchall()
    return {"items": [dict(r) for r in rows], "total": len(rows)}


@app.get("/api/release/releases/{release_id}")
def get_release(release_id: str) -> dict[str, Any]:
    with base.db_ctx() as conn:
        release = conn.execute("SELECT * FROM releases WHERE id=?", (release_id,)).fetchone()
        if not release:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "发布不存在")
        deployments = conn.execute("SELECT * FROM deployments WHERE release_id=? ORDER BY created_at DESC", (release_id,)).fetchall()
    return {**dict(release), "deployments": [dict(r) for r in deployments]}


@app.post("/api/release/releases/{release_id}/deploy", status_code=status.HTTP_201_CREATED)
def deploy(release_id: str, payload: DeployIn, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    deployment_id = str(uuid.uuid4())
    with base.db_ctx() as conn:
        release = conn.execute("SELECT * FROM releases WHERE id=?", (release_id,)).fetchone()
        if not release:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "发布不存在")
        if release["status"] == "rolled_back":
            raise HTTPException(status.HTTP_409_CONFLICT, "已回滚版本不可再部署")
        pipeline = conn.execute("SELECT * FROM pipelines WHERE id=?", (release["pipeline_id"],)).fetchone()
        environments = json.loads(pipeline["environments"])
        if payload.environment not in environments:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "目标环境不在流水线环境中")
        conn.execute("INSERT INTO deployments (id, release_id, environment, status, deployed_by, deployed_at, created_at) VALUES (?,?,?,?,?,?,?)", (deployment_id, release_id, payload.environment, "success", payload.deployed_by, _now(), _now()))
        conn.execute("UPDATE releases SET status='deployed', started_at=COALESCE(started_at,?), finished_at=? WHERE id=?", (_now(), _now(), release_id))
        base.record_audit("release.deployed", payload.deployed_by, f"release={release_id} env={payload.environment}", getattr(request.state, "request_id", ""), getattr(request.state, "trace_id", ""), SERVICE)
    return {"id": deployment_id, "release_id": release_id, "environment": payload.environment, "status": "success"}


@app.post("/api/release/releases/{release_id}/rollback")
def rollback(release_id: str, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    with base.db_ctx() as conn:
        release = conn.execute("SELECT * FROM releases WHERE id=?", (release_id,)).fetchone()
        if not release:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "发布不存在")
        if release["status"] != "deployed":
            raise HTTPException(status.HTTP_409_CONFLICT, "仅已部署版本可回滚")
        conn.execute("UPDATE releases SET status='rolled_back', finished_at=? WHERE id=?", (_now(), release_id))
        conn.execute("UPDATE deployments SET status='rolled_back' WHERE release_id=? AND status='success'", (release_id,))
        base.record_audit("release.rolled_back", "internal", f"release={release_id}", getattr(request.state, "request_id", ""), getattr(request.state, "trace_id", ""), SERVICE)
    return {"id": release_id, "status": "rolled_back"}


@app.get("/api/release/stats")
def stats() -> dict[str, Any]:
    with base.db_ctx() as conn:
        def _count(sql: str) -> int:
            return conn.execute(sql).fetchone()[0]
        return {
            "pipelines": _count("SELECT COUNT(*) FROM pipelines"),
            "releases": _count("SELECT COUNT(*) FROM releases"),
            "deployed": _count("SELECT COUNT(*) FROM releases WHERE status='deployed'"),
            "rolled_back": _count("SELECT COUNT(*) FROM releases WHERE status='rolled_back'"),
            "deployments": _count("SELECT COUNT(*) FROM deployments"),
            "successful_deployments": _count("SELECT COUNT(*) FROM deployments WHERE status='success'"),
        }
