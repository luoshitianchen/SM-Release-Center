"""发布单仓储层。"""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.release_order import ReleaseOrder


async def get_order(session: AsyncSession, order_id: str) -> ReleaseOrder | None:
    result = await session.execute(select(ReleaseOrder).where(ReleaseOrder.id == order_id))
    return result.scalar_one_or_none()


async def get_order_by_no(session: AsyncSession, release_no: str) -> ReleaseOrder | None:
    result = await session.execute(select(ReleaseOrder).where(ReleaseOrder.release_no == release_no))
    return result.scalar_one_or_none()


async def list_orders(
    session: AsyncSession, limit: int = 100, offset: int = 0,
    status: str | None = None, env_id: str | None = None, keyword: str | None = None,
) -> list[ReleaseOrder]:
    stmt = select(ReleaseOrder).order_by(ReleaseOrder.created_at.desc()).limit(limit).offset(offset)
    if status:
        stmt = stmt.where(ReleaseOrder.status == status)
    if env_id:
        stmt = stmt.where(ReleaseOrder.env_id == env_id)
    if keyword:
        pattern = f"%{keyword}%"
        stmt = stmt.where(
            or_(
                ReleaseOrder.release_no.like(pattern),
                ReleaseOrder.title.like(pattern),
                ReleaseOrder.service_name.like(pattern),
            )
        )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_orders(
    session: AsyncSession, status: str | None = None,
    env_id: str | None = None, keyword: str | None = None,
) -> int:
    stmt = select(func.count(ReleaseOrder.id))
    if status:
        stmt = stmt.where(ReleaseOrder.status == status)
    if env_id:
        stmt = stmt.where(ReleaseOrder.env_id == env_id)
    if keyword:
        pattern = f"%{keyword}%"
        stmt = stmt.where(
            or_(
                ReleaseOrder.release_no.like(pattern),
                ReleaseOrder.title.like(pattern),
                ReleaseOrder.service_name.like(pattern),
            )
        )
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def create_order(session: AsyncSession, order: ReleaseOrder) -> ReleaseOrder:
    session.add(order)
    await session.commit()
    await session.refresh(order)
    return order


async def update_order(session: AsyncSession, order: ReleaseOrder) -> ReleaseOrder:
    await session.commit()
    await session.refresh(order)
    return order
