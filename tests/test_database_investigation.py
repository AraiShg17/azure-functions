"""DB調査機能のテスト。"""

from __future__ import annotations

import json
from typing import Any

import azure.functions as func
import pytest

from database_investigation.handler import handle_investigate_database
from database_investigation.models import DatabaseQuery, DatabaseQueryPlan
from database_investigation.models import DatabaseInvestigationAssessment
from database_investigation.rag import allowed_tables, retrieve_schema_context
from database_investigation.sql_guard import UnsafeQueryError, validate_query_plan


def _request(payload: dict[str, Any]) -> func.HttpRequest:
    return func.HttpRequest(
        method="POST",
        url="/api/investigate_database",
        headers={"Content-Type": "application/json"},
        body=json.dumps(payload, ensure_ascii=False).encode(),
    )


def _payload(*, execute: bool = False) -> dict[str, Any]:
    return {
        "incident": {
            "id": "12",
            "title": "年齢が表示されない",
            "description": "特定ユーザーだけ年齢が空欄です",
        },
        "analysis": {
            "databaseQuestions": ["生年月日が登録されているか"],
        },
        "execute": execute,
    }


def _plan(sql: str = "SELECT birth_date FROM customers WHERE customer_id = %(id)s LIMIT 10") -> DatabaseQueryPlan:
    return DatabaseQueryPlan(
        rationale="生年月日を確認する",
        queries=[DatabaseQuery(
            purpose="生年月日の確認",
            sql=sql,
            parameters={"id": 123},
        )],
    )


def _assessment() -> DatabaseInvestigationAssessment:
    return DatabaseInvestigationAssessment(
        summary="対象顧客の生年月日が登録されていない",
        likelyCause="birth_dateがNULLのため年齢を計算できない",
        evidence=["customers.birth_dateがNULL"],
        problemIdentified=True,
        needsRepositoryInvestigation=False,
        recommendedActions=["生年月日の登録経路を確認する"],
        confidence=0.92,
    )


def test_rag_retrieves_customer_schema() -> None:
    chunks = retrieve_schema_context("特定ユーザーの年齢と生年月日を確認")
    ids = {chunk["id"] for chunk in chunks}
    assert "customers" in ids
    assert "customers" in allowed_tables(chunks)


@pytest.mark.parametrize("sql", [
    "DELETE FROM customers WHERE customer_id = %(id)s LIMIT 1",
    "SELECT * FROM customers; DROP TABLE customers",
    "SELECT * FROM secrets LIMIT 10",
    "SELECT * FROM customers",
    "SELECT * FROM customers LIMIT 101",
])
def test_sql_guard_rejects_unsafe_queries(sql: str) -> None:
    with pytest.raises(UnsafeQueryError):
        validate_query_plan(_plan(sql), {"customers"})


def test_sql_guard_accepts_parameterized_select() -> None:
    validate_query_plan(_plan(), {"customers"})


def test_sql_guard_rejects_parameter_mismatch() -> None:
    plan = _plan("SELECT * FROM customers WHERE customer_id = %(other)s LIMIT 10")
    with pytest.raises(UnsafeQueryError):
        validate_query_plan(plan, {"customers"})


def test_plan_only_response_does_not_connect_to_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "database_investigation.handler.create_query_plan",
        lambda incident, questions, context: _plan(),
    )
    monkeypatch.setattr(
        "database_investigation.handler.execute_plan",
        lambda plan: pytest.fail("DB must not be called in planOnly mode"),
    )
    response = handle_investigate_database(_request(_payload()))
    body = json.loads(response.get_body())
    assert response.status_code == 200
    assert body["success"] is True
    assert body["mode"] == "planOnly"
    assert body["queryResults"] is None
    assert body["databaseInvestigation"] is None
    assert "customers" in body["allowedTables"]


def test_execute_mode_returns_database_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "database_investigation.handler.create_query_plan",
        lambda incident, questions, context: _plan(),
    )
    monkeypatch.setattr(
        "database_investigation.handler.execute_plan",
        lambda plan: [{"purpose": "生年月日の確認", "rows": [{"birth_date": "1990-01-01"}]}],
    )
    monkeypatch.setattr(
        "database_investigation.handler.assess_database_results",
        lambda incident, questions, context, plan, results: _assessment(),
    )
    response = handle_investigate_database(_request(_payload(execute=True)))
    body = json.loads(response.get_body())
    assert response.status_code == 200
    assert body["mode"] == "executed"
    assert body["queryResults"][0]["rows"][0]["birth_date"] == "1990-01-01"
    assert body["databaseInvestigation"] == _assessment().model_dump()


def test_description_is_not_logged(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "ログへ出してはいけないDB調査本文"
    monkeypatch.setattr(
        "database_investigation.handler.create_query_plan",
        lambda incident, questions, context: _plan(),
    )
    payload = _payload()
    payload["incident"]["description"] = secret
    with caplog.at_level("INFO"):
        handle_investigate_database(_request(payload))
    assert secret not in caplog.text
