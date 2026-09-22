"""修正PR作成Functionのテスト。"""

import json

import azure.functions as func

from repository_pull_request.handler import handle_create_repository_pull_request
from repository_pull_request.models import FileChange, PullRequestProposal, PullRequestReview


def _payload(problem_identified=True):
    return {
        "incident": {"id": "21", "title": "年齢が表示されない", "description": "一部だけ空欄"},
        "analysis": {"summary": "年齢表示の問題"},
        "databaseInvestigation": {"databaseInvestigation": {"likelyCause": "birth_dateがNULL"}},
        "repositoryInvestigation": {
            "inspectedFiles": ["src/customer.py"],
            "repositoryInvestigation": {
                "problemIdentified": problem_identified,
                "findings": [{"file": "src/customer.py", "line": 10, "finding": "空文字を返す"}],
            },
        },
    }


def _request(payload):
    return func.HttpRequest(
        method="POST", url="/api/create_repository_pull_request",
        headers={"Content-Type": "application/json"},
        body=json.dumps(payload, ensure_ascii=False).encode(),
    )


def test_creates_pr_only_from_identified_existing_files(monkeypatch):
    proposal = PullRequestProposal(
        title="年齢未登録時の表示を修正",
        body="原因と変更内容",
        changes=[FileChange(path="src/customer.py", content="return '未登録'\n", explanation="空欄を明示")],
    )
    review = PullRequestReview(summary="妥当", issues=[], verdict="COMMENT")
    monkeypatch.setattr("repository_pull_request.handler.fetch_files", lambda paths: [
        {"path": "AGENTS.md", "sha": "a", "content": "rules"},
        {"path": "src/customer.py", "sha": "b", "content": "return ''"},
    ])
    monkeypatch.setattr("repository_pull_request.handler.propose_changes", lambda data, files: proposal)
    monkeypatch.setattr("repository_pull_request.handler.review_changes", lambda data, value: review)
    monkeypatch.setattr("repository_pull_request.handler.create_pull_request", lambda incident_id, value, checked, files: {
        "created": True, "branch": "fix/incident-21", "number": 3,
        "url": "https://github.example/pr/3", "changedFiles": ["src/customer.py"],
        "review": review.model_dump(),
    })
    response = handle_create_repository_pull_request(_request(_payload()))
    body = json.loads(response.get_body())
    assert response.status_code == 201
    assert body["pullRequest"]["branch"] == "fix/incident-21"
    assert body["pullRequest"]["changedFiles"] == ["src/customer.py"]


def test_does_not_create_pr_when_problem_is_not_identified(monkeypatch):
    monkeypatch.setattr("repository_pull_request.handler.fetch_files", lambda paths: (_ for _ in ()).throw(AssertionError()))
    response = handle_create_repository_pull_request(_request(_payload(False)))
    assert response.status_code == 422
    assert json.loads(response.get_body())["created"] is False
