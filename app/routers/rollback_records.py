"""回滚记录查询路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.services.rollback_record import RollbackRecordService

router = APIRouter(prefix="/api/release/rollback-records", tags=["rollback-records"])


@router.get("")
async def list_records(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    release_order_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await RollbackRecordService.list_records(
        session, limit=limit, offset=offset,
        release_order_id=release_order_id, status_filter=status_filter,
    )


@router.get("/{record_id}")
async def get_record(
    record_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await RollbackRecordService.get_record(session, record_id)
