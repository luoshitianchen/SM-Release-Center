"""目标环境管理路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.target_environment import (
    TargetEnvironmentCreate,
    TargetEnvironmentStatusUpdate,
    TargetEnvironmentUpdate,
)
from app.services.target_environment import TargetEnvironmentService

router = APIRouter(prefix="/api/release/environments", tags=["target-environments"])


@router.get("")
async def list_envs(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    keyword: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await TargetEnvironmentService.list_envs(
        session, limit=limit, offset=offset,
        status_filter=status_filter, keyword=keyword,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_env(
    payload: TargetEnvironmentCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await TargetEnvironmentService.create_env(session, payload, request)


@router.get("/{env_id}")
async def get_env(
    env_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await TargetEnvironmentService.get_env(session, env_id)


@router.patch("/{env_id}")
async def update_env(
    env_id: str, payload: TargetEnvironmentUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await TargetEnvironmentService.update_env(session, env_id, payload, request)


@router.patch("/{env_id}/status")
async def update_env_status(
    env_id: str, payload: TargetEnvironmentStatusUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await TargetEnvironmentService.update_status(session, env_id, payload.status, request)


@router.delete("/{env_id}", status_code=status.HTTP_200_OK)
async def delete_env(
    env_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await TargetEnvironmentService.delete_env(session, env_id, request)
