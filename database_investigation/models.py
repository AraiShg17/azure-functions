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


class DatabaseInvestigationAssessment(BaseModel):
    """DB取得結果を元にした障害原因の精査結果。"""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, description="DB調査結果の要約")
    likelyCause: str | None = Field(description="現時点で考えられる原因")
    evidence: list[str] = Field(description="取得データから確認できる根拠")
    problemIdentified: bool = Field(description="DB調査で問題を特定できたか")
    needsRepositoryInvestigation: bool = Field(
        description="追加でソースコード調査が必要か"
    )
    recommendedActions: list[str] = Field(description="次に行うべき対応")
    confidence: float = Field(ge=0.0, le=1.0, description="原因判断の確信度")

    def to_response_dict(self) -> dict[str, Any]:
        return self.model_dump()
