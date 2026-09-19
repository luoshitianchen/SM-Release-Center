"""回滚记录 Pydantic 模型。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RollbackRequest(BaseModel):
    reason: str = Field(default="", max_length=2048)
    target_version: str = Field(default="", max_length=64)
    operator: str = Field(default="", max_length=128)


class RollbackRecordResponse(BaseModel):
    id: str
    release_order_id: str
    release_no: str
    reason: str
    target_version: str
    operator: str
    status: str
    created_at: datetime | str


class RollbackRecordListResponse(BaseModel):
    total: int
    items: list[RollbackRecordResponse]
