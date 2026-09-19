"""回滚记录仓储层。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rollback_record import RollbackRecord


async def get_record(session: AsyncSession, record_id: str) -> RollbackRecord | None:
    result = await session.execute(select(RollbackRecord).where(RollbackRecord.id == record_id))
    return result.scalar_one_or_none()


async def list_records(
    session: AsyncSession, limit: int = 100, offset: int = 0,
    release_order_id: str | None = None, status: str | None = None,
) -> list[RollbackRecord]:
    stmt = select(RollbackRecord).order_by(RollbackRecord.created_at.desc()).limit(limit).offset(offset)
    if release_order_id:
        stmt = stmt.where(RollbackRecord.release_order_id == release_order_id)
    if status:
        stmt = stmt.where(RollbackRecord.status == status)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_records(
    session: AsyncSession, release_order_id: str | None = None,
    status: str | None = None,
) -> int:
    stmt = select(func.count(RollbackRecord.id))
    if release_order_id:
        stmt = stmt.where(RollbackRecord.release_order_id == release_order_id)
    if status:
        stmt = stmt.where(RollbackRecord.status == status)
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def count_records_by_order(session: AsyncSession, release_order_id: str) -> int:
    stmt = select(func.count(RollbackRecord.id)).where(
        RollbackRecord.release_order_id == release_order_id
    )
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def create_record(session: AsyncSession, record: RollbackRecord) -> RollbackRecord:
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record
