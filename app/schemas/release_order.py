"""发布单 Pydantic 模型。"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ReleaseOrderCreate(BaseModel):
    release_no: str = Field(min_length=3, max_length=64)
    title: str = Field(min_length=1, max_length=256)
    service_name: str = Field(min_length=1, max_length=128)
    version: str = Field(default="", max_length=64)
    env_id: str = Field(min_length=1, max_length=64)
    operator: str = Field(default="", max_length=128)
    changelog: str = Field(default="", max_length=8192)


class ReleaseOrderUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=256)
    version: str | None = Field(default=None, max_length=64)
    changelog: str | None = Field(default=None, max_length=8192)


class ReleaseOrderStatusUpdate(BaseModel):
    status: Literal["draft", "approved", "deploying", "deployed", "failed", "canceled", "rolled_back"]


class ReleaseOrderResponse(BaseModel):
    id: str
    release_no: str
    title: str
    service_name: str
    version: str
    env_id: str
    status: str
    operator: str
    changelog: str
    created_at: datetime | str
    updated_at: datetime | str


class ReleaseOrderListResponse(BaseModel):
    total: int
    items: list[ReleaseOrderResponse]
