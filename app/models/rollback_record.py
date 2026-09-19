"""回滚记录模型。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class RollbackRecord(Base):
    """回滚记录：一次发布单回滚操作的留痕。"""

    __tablename__ = "rollback_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    release_order_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    release_no: Mapped[str] = mapped_column(String(64), default="", index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    target_version: Mapped[str] = mapped_column(String(64), default="")
    operator: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[str] = mapped_column(String(16), default="success", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
