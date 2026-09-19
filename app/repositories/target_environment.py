"""目标环境仓储层。"""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.target_environment import TargetEnvironment


async def get_env(session: AsyncSession, env_id: str) -> TargetEnvironment | None:
    result = await session.execute(select(TargetEnvironment).where(TargetEnvironment.id == env_id))
    return result.scalar_one_or_none()


async def get_env_by_name(session: AsyncSession, name: str) -> TargetEnvironment | None:
    result = await session.execute(select(TargetEnvironment).where(TargetEnvironment.name == name))
    return result.scalar_one_or_none()


async def list_envs(
    session: AsyncSession, limit: int = 100, offset: int = 0,
    status: str | None = None, keyword: str | None = None,
) -> list[TargetEnvironment]:
    stmt = select(TargetEnvironment).order_by(TargetEnvironment.created_at.desc()).limit(limit).offset(offset)
    if status:
        stmt = stmt.where(TargetEnvironment.status == status)
    if keyword:
        pattern = f"%{keyword}%"
        stmt = stmt.where(
            or_(TargetEnvironment.name.like(pattern), TargetEnvironment.cluster.like(pattern))
        )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_envs(
    session: AsyncSession, status: str | None = None, keyword: str | None = None,
) -> int:
    stmt = select(func.count(TargetEnvironment.id))
    if status:
        stmt = stmt.where(TargetEnvironment.status == status)
    if keyword:
        pattern = f"%{keyword}%"
        stmt = stmt.where(
            or_(TargetEnvironment.name.like(pattern), TargetEnvironment.cluster.like(pattern))
        )
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def create_env(session: AsyncSession, env: TargetEnvironment) -> TargetEnvironment:
    session.add(env)
    await session.commit()
    await session.refresh(env)
    return env


async def update_env(session: AsyncSession, env: TargetEnvironment) -> TargetEnvironment:
    await session.commit()
    await session.refresh(env)
    return env


async def delete_env(session: AsyncSession, env: TargetEnvironment) -> None:
    await session.delete(env)
    await session.commit()
