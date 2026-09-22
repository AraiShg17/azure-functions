"""DB調査で使用する構造化データモデル。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DatabaseQueryParameter(BaseModel):
    """SQLへ渡す名前付きパラメータ。"""

    model_config = ConfigDict(extra="forbid")

    name: str
    value: str = Field(description="SQLへ直接埋め込まずバインドする値")


class DatabaseQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: str
    selectedColumns: list[str] = Field(
        description="調査に必要なため取得する列名",
    )
    dataMinimizationReason: str = Field(
        description="取得列と取得範囲を必要最小限にした理由",
    )
    sql: str = Field(description="名前付きパラメータを使う単一SELECT")
    parameters: list[DatabaseQueryParameter]

    def parameter_dict(self) -> dict[str, str]:
        """PyMySQLへ渡せる辞書へ変換する。"""
        return {parameter.name: parameter.value for parameter in self.parameters}


class DatabaseQueryPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rationale: str
    queries: list[DatabaseQuery]

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
