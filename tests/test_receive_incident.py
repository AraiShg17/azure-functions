"""receive_incident 関数のテスト。"""

from __future__ import annotations

import json
import logging
from typing import Any

import azure.functions as func
import pytest

from incident.analyzer import AnalysisConfigurationError, AnalysisServiceError
from incident.handler import handle_receive_incident
from incident.models import IncidentAnalysis
from function_app import app, receive_incident


def _analysis() -> IncidentAnalysis:
    return IncidentAnalysis(
        summary="ログイン操作で500エラーが発生している",
        needsDatabaseInvestigation=True,
        databaseQuestions=["対象ユーザーの状態が有効か"],
        needsRepositoryInvestigation=True,
        repositoryQuestions=["ログイン処理の直近変更を確認する"],
        confidence=0.4,
    )


@pytest.fixture(autouse=True)
def stub_ai_analysis(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTPハンドラーのテストでは外部APIを呼ばない。"""
    monkeypatch.setattr("incident.handler.analyze_incident", lambda incident: _analysis())


def _make_request(
    body: str | bytes | None,
    content_type: str = "application/json",
) -> func.HttpRequest:
    """テスト用 HttpRequest を生成する。"""
    if isinstance(body, str):
        body_bytes = body.encode("utf-8")
    else:
        body_bytes = body

    return func.HttpRequest(
        method="POST",
        url="/api/receive_incident",
        headers={"Content-Type": content_type},
        body=body_bytes,
    )


def _valid_payload() -> dict[str, Any]:
    return {
        "id": "1",
        "title": "ログイン画面でエラーが発生する",
        "description": "ログインボタンを押すと500エラーになります",
        "category": "障害",
        "createdAt": "2026-09-21T15:00:00+09:00",
    }


def test_valid_json_returns_200() -> None:
    """正常な JSON で HTTP 200 になる。"""
    req = _make_request(json.dumps(_valid_payload(), ensure_ascii=False))
    response = receive_incident(req)

    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/json; charset=utf-8"
    assert "障害情報を受信しました".encode("utf-8") in response.get_body()

    body = json.loads(response.get_body().decode("utf-8"))
    assert body == {
        "success": True,
        "message": "障害情報を受信しました",
        "incident": {
            "id": "1",
            "title": "ログイン画面でエラーが発生する",
            "category": "障害",
        },
        "analysis": _analysis().model_dump(),
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "タイトル", "description": "説明"},
        {"id": "1", "description": "説明"},
        {"id": "1", "title": "タイトル"},
    ],
)
def test_missing_required_field_returns_400(payload: dict[str, Any]) -> None:
    """必須項目不足で HTTP 400 になる。"""
    req = _make_request(json.dumps(payload, ensure_ascii=False))
    response = handle_receive_incident(req)

    assert response.status_code == 400
    body = json.loads(response.get_body().decode("utf-8"))
    assert body["success"] is False
    assert "message" in body


@pytest.mark.parametrize(
    "payload",
    [
        {"id": "", "title": "タイトル", "description": "説明"},
        {"id": "1", "title": "", "description": "説明"},
        {"id": "1", "title": "タイトル", "description": ""},
        {"id": "   ", "title": "タイトル", "description": "説明"},
    ],
)
def test_empty_required_field_returns_400(payload: dict[str, Any]) -> None:
    """空文字で HTTP 400 になる。"""
    req = _make_request(json.dumps(payload, ensure_ascii=False))
    response = handle_receive_incident(req)

    assert response.status_code == 400
    body = json.loads(response.get_body().decode("utf-8"))
    assert body["success"] is False


def test_invalid_json_returns_400() -> None:
    """不正な JSON で HTTP 400 になる。"""
    req = _make_request("{invalid json")
    response = handle_receive_incident(req)

    assert response.status_code == 400
    body = json.loads(response.get_body().decode("utf-8"))
    assert body["success"] is False


def test_non_object_json_returns_400() -> None:
    """JSON オブジェクト以外で HTTP 400 になる。"""
    req = _make_request(json.dumps(["not", "an", "object"]))
    response = handle_receive_incident(req)

    assert response.status_code == 400
    body = json.loads(response.get_body().decode("utf-8"))
    assert body["success"] is False


def test_invalid_content_type_returns_400() -> None:
    """Content-Type が application/json でない場合 HTTP 400 になる。"""
    req = _make_request(
        json.dumps(_valid_payload(), ensure_ascii=False),
        content_type="text/plain",
    )
    response = handle_receive_incident(req)

    assert response.status_code == 400
    body = json.loads(response.get_body().decode("utf-8"))
    assert body["success"] is False


def test_description_is_not_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """description がログへ出力されない。"""
    payload = _valid_payload()
    secret_description = "この説明文はログに出してはいけない機密情報"

    with caplog.at_level(logging.INFO):
        req = _make_request(
            json.dumps(
                {**payload, "description": secret_description},
                ensure_ascii=False,
            )
        )
        handle_receive_incident(req)

    log_text = caplog.text
    assert secret_description not in log_text
    assert "SharePoint項目ID: 1" in log_text
    assert "タイトル: ログイン画面でエラーが発生する" in log_text


@pytest.mark.parametrize("body", ["null", "true", "123", '"text"', "", b"\xff"])
def test_other_invalid_bodies_return_400(body: str | bytes) -> None:
    response = receive_incident(_make_request(body))
    assert response.status_code == 400
    assert response.headers["Content-Type"] == "application/json; charset=utf-8"
    assert json.loads(response.get_body())["success"] is False


@pytest.mark.parametrize("field", ["id", "title", "description"])
@pytest.mark.parametrize("value", [None, 123, False, [], {}, " \t\n"])
def test_required_fields_must_be_nonblank_strings(field: str, value: Any) -> None:
    payload = {**_valid_payload(), field: value}
    assert receive_incident(_make_request(json.dumps(payload))).status_code == 400


@pytest.mark.parametrize("content_type", ["", "text/json", "application/jsonp"])
def test_missing_or_wrong_content_type(content_type: str) -> None:
    response = receive_incident(_make_request(json.dumps(_valid_payload()), content_type))
    assert response.status_code == 400


def test_json_content_type_with_charset() -> None:
    response = receive_incident(_make_request(
        json.dumps(_valid_payload()), "Application/JSON; charset=utf-8"
    ))
    assert response.status_code == 200


def test_optional_fields_can_be_omitted() -> None:
    payload = {key: _valid_payload()[key] for key in ("id", "title", "description")}
    response = receive_incident(_make_request(json.dumps(payload)))
    assert response.status_code == 200
    assert json.loads(response.get_body())["incident"]["category"] is None


def test_unexpected_exception_is_sanitized(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "例外に含まれる機密の障害本文"

    def fail(
        incident: dict[str, Any],
        analysis: IncidentAnalysis,
    ) -> func.HttpResponse:
        raise RuntimeError(incident["description"])

    monkeypatch.setattr("incident.handler.success_response", fail)
    with caplog.at_level(logging.INFO):
        response = receive_incident(_make_request(json.dumps({
            **_valid_payload(), "description": secret,
        })))
    assert response.status_code == 500
    assert response.headers["Content-Type"] == "application/json; charset=utf-8"
    assert json.loads(response.get_body()) == {
        "success": False, "message": "内部サーバーエラーが発生しました",
    }
    assert secret not in response.get_body().decode("utf-8")
    assert secret not in caplog.text
    assert "Traceback" not in caplog.text
    assert "異常終了" in caplog.text


def test_ai_configuration_error_is_sanitized(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def fail(incident: dict[str, Any]) -> IncidentAnalysis:
        raise AnalysisConfigurationError(incident["description"])

    monkeypatch.setattr("incident.handler.analyze_incident", fail)
    secret = "AI設定エラーへ含めてはいけない障害本文"
    with caplog.at_level(logging.INFO):
        response = receive_incident(_make_request(json.dumps({
            **_valid_payload(), "description": secret,
        })))

    assert response.status_code == 500
    assert json.loads(response.get_body()) == {
        "success": False,
        "message": "AI分析の設定が完了していません",
    }
    assert secret not in response.get_body().decode("utf-8")
    assert secret not in caplog.text


def test_ai_service_error_returns_502_without_details(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def fail(incident: dict[str, Any]) -> IncidentAnalysis:
        raise AnalysisServiceError(incident["description"])

    monkeypatch.setattr("incident.handler.analyze_incident", fail)
    secret = "外部サービスエラーへ含めてはいけない障害本文"
    with caplog.at_level(logging.INFO):
        response = receive_incident(_make_request(json.dumps({
            **_valid_payload(), "description": secret,
        })))

    assert response.status_code == 502
    assert json.loads(response.get_body()) == {
        "success": False,
        "message": "AI分析に失敗しました",
    }
    assert secret not in response.get_body().decode("utf-8")
    assert secret not in caplog.text


def test_validation_failure_does_not_log_description(caplog: pytest.LogCaptureFixture) -> None:
    secret = "検証失敗時にも記録しない本文"
    with caplog.at_level(logging.INFO):
        response = receive_incident(_make_request(json.dumps({
            "id": "1", "description": secret,
        })))
    assert response.status_code == 400
    assert secret not in caplog.text
    assert "異常終了" in caplog.text


def test_function_registration() -> None:
    functions = app.get_functions()
    assert len(functions) == 5
    registered = {function.get_function_name(): function for function in functions}
    assert set(registered) == {
        "receive_incident",
        "investigate_database",
        "create_backlog_issue",
        "investigate_repository",
        "create_repository_pull_request",
    }
    trigger = registered["receive_incident"].get_trigger().get_dict_repr()
    assert trigger["route"] == "receive_incident"
    assert trigger["methods"] == [func.HttpMethod.POST]
    assert trigger["authLevel"] == func.AuthLevel.FUNCTION

    investigation_trigger = registered["investigate_database"].get_trigger().get_dict_repr()
    assert investigation_trigger["route"] == "investigate_database"
    assert investigation_trigger["methods"] == [func.HttpMethod.POST]
    assert investigation_trigger["authLevel"] == func.AuthLevel.FUNCTION

    backlog_trigger = registered["create_backlog_issue"].get_trigger().get_dict_repr()
    assert backlog_trigger["route"] == "create_backlog_issue"
    assert backlog_trigger["methods"] == [func.HttpMethod.POST]
    assert backlog_trigger["authLevel"] == func.AuthLevel.FUNCTION

    repository_trigger = registered["investigate_repository"].get_trigger().get_dict_repr()
    assert repository_trigger["route"] == "investigate_repository"
    assert repository_trigger["methods"] == [func.HttpMethod.POST]
    assert repository_trigger["authLevel"] == func.AuthLevel.FUNCTION

    pull_request_trigger = registered["create_repository_pull_request"].get_trigger().get_dict_repr()
    assert pull_request_trigger["route"] == "create_repository_pull_request"
    assert pull_request_trigger["methods"] == [func.HttpMethod.POST]
    assert pull_request_trigger["authLevel"] == func.AuthLevel.FUNCTION
