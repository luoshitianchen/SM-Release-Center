"""目标环境 Pydantic 模型。"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TargetEnvironmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=64)
    cluster: str = Field(default="", max_length=128)
    region: str = Field(default="cn-east-1", max_length=64)


class TargetEnvironmentUpdate(BaseModel):
    cluster: str | None = Field(default=None, max_length=128)
    region: str | None = Field(default=None, max_length=64)


class TargetEnvironmentStatusUpdate(BaseModel):
    status: Literal["active", "maintenance"]


class TargetEnvironmentResponse(BaseModel):
    id: str
    name: str
    cluster: str
    region: str
    status: str
    created_at: datetime | str
    updated_at: datetime | str


class TargetEnvironmentListResponse(BaseModel):
    total: int
    items: list[TargetEnvironmentResponse]
