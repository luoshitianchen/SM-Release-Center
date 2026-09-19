"""发布单管理路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.release_order import (
    ReleaseOrderCreate,
    ReleaseOrderStatusUpdate,
    ReleaseOrderUpdate,
)
from app.schemas.rollback_record import RollbackRequest
from app.services.release_order import ReleaseOrderService

router = APIRouter(prefix="/api/release/orders", tags=["release-orders"])


@router.get("")
async def list_orders(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    env_id: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await ReleaseOrderService.list_orders(
        session, limit=limit, offset=offset, status_filter=status_filter,
        env_id=env_id, keyword=keyword,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: ReleaseOrderCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await ReleaseOrderService.create_order(session, payload, request)


@router.get("/{order_id}")
async def get_order(
    order_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await ReleaseOrderService.get_order(session, order_id)


@router.patch("/{order_id}")
async def update_order(
    order_id: str, payload: ReleaseOrderUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await ReleaseOrderService.update_order(session, order_id, payload, request)


@router.patch("/{order_id}/status")
async def update_order_status(
    order_id: str, payload: ReleaseOrderStatusUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await ReleaseOrderService.update_status(session, order_id, payload.status, request)


@router.post("/{order_id}/rollback", status_code=status.HTTP_200_OK)
async def rollback_order(
    order_id: str, payload: RollbackRequest, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await ReleaseOrderService.rollback(session, order_id, payload, request)
