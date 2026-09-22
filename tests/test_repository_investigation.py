"""リポジトリ調査Functionのテスト。"""

from __future__ import annotations

import json

import azure.functions as func

from repository_investigation.handler import handle_investigate_repository
from repository_investigation.models import (
    RepositoryAssessment,
    RepositoryFinding,
    RepositorySearchPlan,
)


def _payload() -> dict:
    return {
        "incident": {
            "id": "21",
            "title": "一部ユーザーの年齢が表示されない",
            "description": "ユーザー情報で年齢が空欄になる",
        },
        "analysis": {
            "repositoryQuestions": ["年齢表示処理を確認する"],
        },
        "databaseInvestigation": {
            "queryPlan": {"queries": []},
            "databaseInvestigation": {
                "likelyCause": "birth_dateがNULL",
            },
        },
    }


def _request(payload: dict) -> func.HttpRequest:
    return func.HttpRequest(
        method="POST",
        url="/api/investigate_repository",
        headers={"Content-Type": "application/json"},
        body=json.dumps(payload, ensure_ascii=False).encode(),
    )


def test_repository_investigation_returns_traceable_result(monkeypatch) -> None:
    plan = RepositorySearchPlan(
        rationale="年齢算出元を探す",
        searchTerms=["birth_date", "show_age"],
    )
    monkeypatch.setattr(
        "repository_investigation.handler.create_search_plan", lambda data: plan
    )
    monkeypatch.setattr(
        "repository_investigation.handler.search_and_fetch",
        lambda terms: (
            ["src/customer.py"],
            [{
                "path": "src/customer.py",
                "startLine": 40,
                "endLine": 80,
                "content": "if birth_date is None: return ''",
            }],
        ),
    )
    monkeypatch.setattr(
        "repository_investigation.handler.assess_repository",
        lambda data, search_plan, snippets: RepositoryAssessment(
            summary="NULL時に空文字を返している",
            findings=[RepositoryFinding(
                file="src/customer.py",
                line=52,
                finding="年齢を空欄にする分岐がある",
                evidence="if birth_date is None",
            )],
            likelyCause="NULL時の表示仕様",
            problemIdentified=True,
            recommendedChanges=["未登録と表示する"],
            confidence=0.9,
        ),
    )
    response = handle_investigate_repository(_request(_payload()))
    body = json.loads(response.get_body())
    assert response.status_code == 200
    assert body["searchPlan"]["searchTerms"] == ["birth_date", "show_age"]
    assert body["inspectedFiles"] == ["src/customer.py"]
    assert body["codeSnippets"] == [{
        "path": "src/customer.py", "startLine": 40, "endLine": 80,
    }]
    assert body["repositoryInvestigation"]["findings"][0]["line"] == 52
    assert "content" not in json.dumps(body["codeSnippets"])


def test_repository_request_accepts_stringified_db_result(monkeypatch) -> None:
    payload = _payload()
    payload["databaseInvestigation"] = json.dumps(payload["databaseInvestigation"])
    monkeypatch.setattr(
        "repository_investigation.handler.create_search_plan",
        lambda data: RepositorySearchPlan(rationale="調査", searchTerms=["age"]),
    )
    monkeypatch.setattr(
        "repository_investigation.handler.search_and_fetch", lambda terms: ([], [])
    )
    monkeypatch.setattr(
        "repository_investigation.handler.assess_repository",
        lambda *args: RepositoryAssessment(
            summary="証拠なし", findings=[], likelyCause=None,
            problemIdentified=False, recommendedChanges=[], confidence=0,
        ),
    )
    assert handle_investigate_repository(_request(payload)).status_code == 200
