"""障害の一次分析で使用するデータモデル。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class IncidentAnalysis(BaseModel):
    """AIが返す障害の一次分析結果。"""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, description="障害内容の簡潔な要約")
    needsDatabaseInvestigation: bool = Field(
        description="原因特定のためにDB調査が必要か"
    )
    databaseQuestions: list[str] = Field(
        description="DB調査で確認すべき具体的な質問"
    )
    needsRepositoryInvestigation: bool = Field(
        description="原因特定のためにソースコード調査が必要か"
    )
    repositoryQuestions: list[str] = Field(
        description="リポジトリ調査で確認すべき具体的な質問"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="現時点の原因推定に対する確信度",
    )

    def to_response_dict(self) -> dict[str, Any]:
        """HTTPレスポンス用のJSON互換dictへ変換する。"""
        return self.model_dump()
