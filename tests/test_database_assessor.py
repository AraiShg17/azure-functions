"""DB取得結果のAI精査テスト。"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import Any

import pytest

from database_investigation.assessor import (
    AssessmentConfigurationError,
    AssessmentServiceError,
    assess_database_results,
)
from database_investigation.models import (
    DatabaseInvestigationAssessment,
    DatabaseQuery,
    DatabaseQueryPlan,
)


def _assessment() -> DatabaseInvestigationAssessment:
    return DatabaseInvestigationAssessment(
        summary="生年月日が未登録",
        likelyCause="年齢算出元のbirth_dateがNULL",
        evidence=["customers.birth_dateがNULL"],
        problemIdentified=True,
        needsRepositoryInvestigation=False,
        recommendedActions=["登録経路を確認する"],
        confidence=0.9,
    )


def _plan() -> DatabaseQueryPlan:
    return DatabaseQueryPlan(
        rationale="生年月日を確認",
        queries=[DatabaseQuery(
            purpose="生年月日確認",
            sql="SELECT birth_date FROM customers WHERE customer_id=%(id)s LIMIT 1",
            parameters={"id": 1},
        )],
    )


def test_assessment_uses_structured_output(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class FakeResponses:
        def parse(self, **kwargs: Any) -> SimpleNamespace:
            captured.update(kwargs)
            return SimpleNamespace(output_parsed=_assessment())

    class FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            captured["client"] = kwargs
            self.responses = FakeResponses()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setattr("database_investigation.assessor.OpenAI", FakeClient)
    result = assess_database_results(
        {"id": "1", "title": "年齢が空欄", "description": "一部顧客のみ"},
        ["生年月日があるか"],
        [{"id": "customers", "content": "birth_date DATE NULL可"}],
        _plan(),
        [{"purpose": "生年月日確認", "rows": [{"birth_date": date(1990, 1, 1)}]}],
    )
    assert result == _assessment()
    assert captured["text_format"] is DatabaseInvestigationAssessment
    assert captured["store"] is False
    assert "1990-01-01" in captured["input"]


def test_missing_openai_settings_is_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    with pytest.raises(AssessmentConfigurationError):
        assess_database_results({}, [], [], _plan(), [])


def test_empty_ai_output_is_service_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponses:
        def parse(self, **kwargs: Any) -> SimpleNamespace:
            return SimpleNamespace(output_parsed=None)

    class FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            self.responses = FakeResponses()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setattr("database_investigation.assessor.OpenAI", FakeClient)
    with pytest.raises(AssessmentServiceError):
        assess_database_results({}, [], [], _plan(), [])
