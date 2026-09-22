"""リポジトリ調査の構造化モデル。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RepositorySearchPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rationale: str
    searchTerms: list[str] = Field(min_length=1, max_length=8)


class RepositoryFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: str
    line: int = Field(ge=1)
    finding: str
    evidence: str


class RepositoryAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    findings: list[RepositoryFinding]
    likelyCause: str | None
    problemIdentified: bool
    recommendedChanges: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
