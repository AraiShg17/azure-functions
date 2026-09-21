"""OpenAIを使用した一次分析のテスト。"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from incident.analyzer import (
    AnalysisConfigurationError,
    AnalysisServiceError,
    analyze_incident,
)
from incident.models import IncidentAnalysis
from incident.prompts import build_analysis_input


def _incident() -> dict[str, Any]:
    return {
        "id": "8",
        "title": "サイトが404",
        "description": "本番サイトにアクセスしたら404表示でした",
    }


def _analysis() -> IncidentAnalysis:
    return IncidentAnalysis(
        summary="本番サイトの特定ページで404が発生",
        needsDatabaseInvestigation=True,
        databaseQuestions=["URLに対応するページレコードが存在するか"],
        needsRepositoryInvestigation=True,
        repositoryQuestions=["対象URLのルーティング定義が存在するか"],
        confidence=0.45,
    )


def test_build_analysis_input_contains_incident_as_json() -> None:
    result = build_analysis_input(_incident())
    assert '"id": "8"' in result
    assert '"title": "サイトが404"' in result
    assert '"description": "本番サイトにアクセスしたら404表示でした"' in result
    assert '"category": null' in result


def test_missing_api_key_is_configuration_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    with pytest.raises(AnalysisConfigurationError):
        analyze_incident(_incident())


def test_missing_model_is_configuration_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    with pytest.raises(AnalysisConfigurationError):
        analyze_incident(_incident())


def test_structured_analysis_is_returned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeResponses:
        def parse(self, **kwargs: Any) -> SimpleNamespace:
            captured.update(kwargs)
            return SimpleNamespace(output_parsed=_analysis())

    class FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            captured["client"] = kwargs
            self.responses = FakeResponses()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setattr("incident.analyzer.OpenAI", FakeClient)

    result = analyze_incident(_incident())

    assert result == _analysis()
    assert captured["model"] == "test-model"
    assert captured["text_format"] is IncidentAnalysis
    assert captured["store"] is False
    assert captured["client"] == {"api_key": "test-key", "timeout": 30.0}


def test_empty_structured_output_is_service_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponses:
        def parse(self, **kwargs: Any) -> SimpleNamespace:
            return SimpleNamespace(output_parsed=None)

    class FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            self.responses = FakeResponses()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setattr("incident.analyzer.OpenAI", FakeClient)

    with pytest.raises(AnalysisServiceError):
        analyze_incident(_incident())
