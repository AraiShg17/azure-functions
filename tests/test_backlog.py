"""Backlog起票機能のテスト。"""

from __future__ import annotations

import json
from typing import Any

import azure.functions as func

from backlog.handler import handle_create_backlog_issue


def _payload(*, dry_run: bool = True) -> dict[str, Any]:
    return {
        "incident": {
            "id": "12",
            "title": "年齢が表示されない",
            "description": "特定ユーザーだけ年齢が空欄です",
        },
        "analysis": {
            "summary": "年齢の元データまたは表示処理に問題がある可能性がある",
            "databaseQuestions": ["生年月日が登録されているか"],
            "repositoryQuestions": ["年齢算出処理を確認する"],
        },
        "databaseInvestigation": {
            "mode": "simulated",
            "queryPlan": {
                "rationale": "年齢算出元を確認する",
                "queries": [{
                    "purpose": "生年月日の確認",
                    "selectedColumns": ["customers.customer_id", "customers.birth_date"],
                    "dataMinimizationReason": "必要な2列だけ取得する",
                    "sql": "SELECT customer_id, birth_date FROM customers WHERE customer_id=%(id)s LIMIT 1",
                    "parameters": [{"name": "id", "value": "1001"}],
                }],
            },
            "queryResults": [{
                "rowCount": 1,
                "rows": [{"customer_id": 1001, "birth_date": None}],
                "simulated": True,
            }],
            "databaseInvestigation": {
                "summary": "仮データでは生年月日の欠損が確認された",
                "likelyCause": "birth_dateがNULLのため年齢を算出できない",
                "evidence": ["customers.birth_dateがNULL"],
                "problemIdentified": True,
                "needsRepositoryInvestigation": False,
                "recommendedActions": ["登録経路を確認する"],
                "confidence": 0.9,
            },
        },
        "dryRun": dry_run,
    }


def _request(payload: dict[str, Any]) -> func.HttpRequest:
    return func.HttpRequest(
        method="POST",
        url="/api/create_backlog_issue",
        headers={"Content-Type": "application/json"},
        body=json.dumps(payload, ensure_ascii=False).encode(),
    )


def test_preview_contains_issue_sql_rows_and_assessment() -> None:
    response = handle_create_backlog_issue(_request(_payload()))
    body = json.loads(response.get_body())
    assert response.status_code == 200
    assert body["mode"] == "preview"
    assert body["backlogIssue"]["summary"] == "[障害調査] 年齢が表示されない"
    description = body["backlogIssue"]["description"]
    assert "シミュレーション（仮データ" in description
    assert "SELECT customer_id, birth_date" in description
    assert '"birth_date": null' in description
    assert "birth_dateがNULLのため年齢を算出できない" in description


def test_preview_does_not_call_backlog(monkeypatch) -> None:
    monkeypatch.setattr(
        "backlog.handler.create_issue",
        lambda *_: (_ for _ in ()).throw(AssertionError("must not call Backlog")),
    )
    assert handle_create_backlog_issue(_request(_payload())).status_code == 200


def test_create_returns_issue_key(monkeypatch) -> None:
    monkeypatch.setattr(
        "backlog.handler.create_issue",
        lambda summary, description: {
            "id": 123,
            "issueKey": "INC-10",
            "summary": summary,
        },
    )
    response = handle_create_backlog_issue(_request(_payload(dry_run=False)))
    body = json.loads(response.get_body())
    assert response.status_code == 201
    assert body["mode"] == "created"
    assert body["backlogIssue"]["issueKey"] == "INC-10"


def test_rejects_missing_investigation() -> None:
    payload = _payload()
    del payload["databaseInvestigation"]
    response = handle_create_backlog_issue(_request(payload))
    assert response.status_code == 400
