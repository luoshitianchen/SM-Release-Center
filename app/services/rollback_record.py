"""回滚记录服务层：回滚留痕查询。"""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rollback_record import RollbackRecord
from app.repositories import rollback_record as repo


def _record_to_dict(r: RollbackRecord) -> dict:
    return {
        "id": r.id, "release_order_id": r.release_order_id,
        "release_no": r.release_no or "", "reason": r.reason or "",
        "target_version": r.target_version or "", "operator": r.operator or "",
        "status": r.status,
        "created_at": r.created_at.isoformat() if r.created_at else "",
    }


class RollbackRecordService:
    @staticmethod
    async def list_records(
        session: AsyncSession, limit: int = 100, offset: int = 0,
        release_order_id: str | None = None, status_filter: str | None = None,
    ) -> dict:
        items = await repo.list_records(
            session, limit=limit, offset=offset,
            release_order_id=release_order_id, status=status_filter,
        )
        total = await repo.count_records(
            session, release_order_id=release_order_id, status=status_filter
        )
        return {"total": total, "items": [_record_to_dict(r) for r in items]}

    @staticmethod
    async def get_record(session: AsyncSession, record_id: str) -> dict:
        record = await repo.get_record(session, record_id)
        if not record:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "回滚记录不存在")
        return _record_to_dict(record)
