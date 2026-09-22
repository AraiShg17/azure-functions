"""DB調査で使用する構造化データモデル。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DatabaseQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: str = Field(min_length=1)
    sql: str = Field(min_length=1, description="名前付きパラメータを使う単一SELECT")
    parameters: dict[str, str | int | float | bool | None]


class DatabaseQueryPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rationale: str = Field(min_length=1)
    queries: list[DatabaseQuery] = Field(min_length=1, max_length=3)

    def to_response_dict(self) -> dict[str, Any]:
        return self.model_dump()
