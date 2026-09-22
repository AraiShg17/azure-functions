"""PR作成用の構造化モデル。"""

from pydantic import BaseModel, ConfigDict, Field


class FileChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    content: str
    explanation: str


class PullRequestProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    body: str
    changes: list[FileChange] = Field(min_length=1, max_length=3)


class PullRequestReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    issues: list[str]
    verdict: str
