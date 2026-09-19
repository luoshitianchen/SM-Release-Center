"""发布单服务层：发布流程状态机与回滚编排。"""
from __future__ import annotations

import uuid

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import internal_write_allowed
from app.models.release_order import ReleaseOrder
from app.models.rollback_record import RollbackRecord
from app.repositories import release_order as repo
from app.repositories import rollback_record as rb_repo
from app.repositories import target_environment as env_repo
from app.schemas.release_order import ReleaseOrderCreate, ReleaseOrderUpdate
from app.schemas.rollback_record import RollbackRequest
from app.services.audit import record_audit

# 发布单状态机：合法迁移
_ORDER_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"approved", "canceled"},
    "approved": {"deploying", "canceled"},
    "deploying": {"deployed", "failed"},
    "deployed": {"rolled_back"},
    "failed": {"deploying", "rolled_back"},
    "canceled": set(),
    "rolled_back": set(),
}

# 允许发起回滚的状态
_ROLLBACK_ALLOWED = {"deployed", "failed"}


def _order_to_dict(o: ReleaseOrder) -> dict:
    return {
        "id": o.id, "release_no": o.release_no, "title": o.title,
        "service_name": o.service_name, "version": o.version or "",
        "env_id": o.env_id, "status": o.status, "operator": o.operator or "",
        "changelog": o.changelog or "",
        "created_at": o.created_at.isoformat() if o.created_at else "",
        "updated_at": o.updated_at.isoformat() if o.updated_at else "",
    }


class ReleaseOrderService:
    @staticmethod
    async def list_orders(
        session: AsyncSession, limit: int = 100, offset: int = 0,
        status_filter: str | None = None, env_id: str | None = None,
        keyword: str | None = None,
    ) -> dict:
        items = await repo.list_orders(
            session, limit=limit, offset=offset, status=status_filter,
            env_id=env_id, keyword=keyword,
        )
        total = await repo.count_orders(
            session, status=status_filter, env_id=env_id, keyword=keyword
        )
        return {"total": total, "items": [_order_to_dict(o) for o in items]}

    @staticmethod
    async def get_order(session: AsyncSession, order_id: str) -> dict:
        order = await repo.get_order(session, order_id)
        if not order:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "发布单不存在")
        return _order_to_dict(order)

    @staticmethod
    async def create_order(
        session: AsyncSession, payload: ReleaseOrderCreate, request: Request
    ) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        env = await env_repo.get_env(session, payload.env_id)
        if not env:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "目标环境不存在")
        if env.status != "active":
            raise HTTPException(status.HTTP_409_CONFLICT, "仅 active 环境可发起发布")
        if await repo.get_order_by_no(session, payload.release_no):
            raise HTTPException(status.HTTP_409_CONFLICT, "发布单号已存在")
        order = ReleaseOrder(
            id=str(uuid.uuid4()), release_no=payload.release_no, title=payload.title,
            service_name=payload.service_name, version=payload.version,
            env_id=payload.env_id, operator=payload.operator,
            changelog=payload.changelog, status="draft",
        )
        order = await repo.create_order(session, order)
        await record_audit(session, "release.created", "internal",
                           f"no={payload.release_no}", request)
        return _order_to_dict(order)

    @staticmethod
    async def update_order(
        session: AsyncSession, order_id: str, payload: ReleaseOrderUpdate, request: Request
    ) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        order = await repo.get_order(session, order_id)
        if not order:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "发布单不存在")
        if order.status not in ("draft", "approved"):
            raise HTTPException(status.HTTP_409_CONFLICT, "仅 draft/approved 状态可编辑")
        if payload.title is not None:
            order.title = payload.title
        if payload.version is not None:
            order.version = payload.version
        if payload.changelog is not None:
            order.changelog = payload.changelog
        order = await repo.update_order(session, order)
        await record_audit(session, "release.updated", "internal",
                           f"order_id={order_id}", request)
        return _order_to_dict(order)

    @staticmethod
    async def update_status(
        session: AsyncSession, order_id: str, new_status: str, request: Request
    ) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        order = await repo.get_order(session, order_id)
        if not order:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "发布单不存在")
        allowed = _ORDER_TRANSITIONS.get(order.status, set())
        if new_status not in allowed:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"非法状态迁移：{order.status} -> {new_status}",
            )
        order.status = new_status
        order = await repo.update_order(session, order)
        await record_audit(session, "release.status_changed", "internal",
                           f"order_id={order_id} status={new_status}", request)
        return _order_to_dict(order)

    @staticmethod
    async def rollback(
        session: AsyncSession, order_id: str, payload: RollbackRequest, request: Request
    ) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        order = await repo.get_order(session, order_id)
        if not order:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "发布单不存在")
        if order.status not in _ROLLBACK_ALLOWED:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"当前状态 {order.status} 不可回滚",
            )
        record = RollbackRecord(
            id=str(uuid.uuid4()), release_order_id=order.id,
            release_no=order.release_no, reason=payload.reason,
            target_version=payload.target_version or order.version,
            operator=payload.operator or order.operator, status="success",
        )
        await rb_repo.create_record(session, record)
        order.status = "rolled_back"
        order = await repo.update_order(session, order)
        await record_audit(session, "release.rolled_back", "internal",
                           f"order_id={order_id} record_id={record.id}", request)
        return {
            "order": _order_to_dict(order),
            "rollback": {
                "id": record.id, "target_version": record.target_version,
                "status": record.status,
            },
        }
