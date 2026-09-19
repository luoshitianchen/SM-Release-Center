"""目标环境服务层：环境登记与维护。"""
from __future__ import annotations

import uuid

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import internal_write_allowed
from app.models.target_environment import TargetEnvironment
from app.repositories import release_order as order_repo
from app.repositories import target_environment as repo
from app.schemas.target_environment import TargetEnvironmentCreate, TargetEnvironmentUpdate
from app.services.audit import record_audit


def _env_to_dict(e: TargetEnvironment) -> dict:
    return {
        "id": e.id, "name": e.name, "cluster": e.cluster or "",
        "region": e.region, "status": e.status,
        "created_at": e.created_at.isoformat() if e.created_at else "",
        "updated_at": e.updated_at.isoformat() if e.updated_at else "",
    }


class TargetEnvironmentService:
    @staticmethod
    async def list_envs(
        session: AsyncSession, limit: int = 100, offset: int = 0,
        status_filter: str | None = None, keyword: str | None = None,
    ) -> dict:
        items = await repo.list_envs(
            session, limit=limit, offset=offset, status=status_filter, keyword=keyword
        )
        total = await repo.count_envs(session, status=status_filter, keyword=keyword)
        return {"total": total, "items": [_env_to_dict(e) for e in items]}

    @staticmethod
    async def get_env(session: AsyncSession, env_id: str) -> dict:
        env = await repo.get_env(session, env_id)
        if not env:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "目标环境不存在")
        return _env_to_dict(env)

    @staticmethod
    async def create_env(
        session: AsyncSession, payload: TargetEnvironmentCreate, request: Request
    ) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        if await repo.get_env_by_name(session, payload.name):
            raise HTTPException(status.HTTP_409_CONFLICT, "环境名已存在")
        env = TargetEnvironment(
            id=str(uuid.uuid4()), name=payload.name, cluster=payload.cluster,
            region=payload.region, status="active",
        )
        env = await repo.create_env(session, env)
        await record_audit(session, "env.created", "internal",
                           f"env={payload.name}", request)
        return _env_to_dict(env)

    @staticmethod
    async def update_env(
        session: AsyncSession, env_id: str, payload: TargetEnvironmentUpdate, request: Request
    ) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        env = await repo.get_env(session, env_id)
        if not env:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "目标环境不存在")
        if payload.cluster is not None:
            env.cluster = payload.cluster
        if payload.region is not None:
            env.region = payload.region
        env = await repo.update_env(session, env)
        await record_audit(session, "env.updated", "internal",
                           f"env_id={env_id}", request)
        return _env_to_dict(env)

    @staticmethod
    async def update_status(
        session: AsyncSession, env_id: str, new_status: str, request: Request
    ) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        env = await repo.get_env(session, env_id)
        if not env:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "目标环境不存在")
        if new_status not in ("active", "maintenance"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "非法状态值")
        env.status = new_status
        env = await repo.update_env(session, env)
        await record_audit(session, "env.status_changed", "internal",
                           f"env_id={env_id} status={new_status}", request)
        return _env_to_dict(env)

    @staticmethod
    async def delete_env(session: AsyncSession, env_id: str, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        env = await repo.get_env(session, env_id)
        if not env:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "目标环境不存在")
        # 环境下存在发布单时禁止删除
        order_total = await order_repo.count_orders(session, env_id=env_id)
        if order_total > 0:
            raise HTTPException(status.HTTP_409_CONFLICT, "环境下存在发布单，禁止删除")
        name = env.name
        await repo.delete_env(session, env)
        await record_audit(session, "env.deleted", "internal",
                           f"env_id={env_id} name={name}", request)
        return {"deleted": True, "id": env_id}
