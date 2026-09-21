"""OpenAI APIを使用した障害の一次分析。"""

from __future__ import annotations

import os
from typing import Any

from openai import OpenAI, OpenAIError

from incident.models import IncidentAnalysis
from incident.prompts import ANALYSIS_INSTRUCTIONS, build_analysis_input

DEFAULT_TIMEOUT_SECONDS = 30.0


class AnalysisConfigurationError(Exception):
    """一次分析に必要な設定が不足している。"""


class AnalysisServiceError(Exception):
    """外部AIサービスによる一次分析に失敗した。"""


def _required_setting(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise AnalysisConfigurationError(f"{name} is not configured")
    return value


def analyze_incident(incident: dict[str, Any]) -> IncidentAnalysis:
    """障害情報をOpenAIへ送り、型付きの一次分析結果を返す。"""
    api_key = _required_setting("OPENAI_API_KEY")
    model = _required_setting("OPENAI_MODEL")

    try:
        timeout = float(os.getenv("OPENAI_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS))
    except ValueError as exc:
        raise AnalysisConfigurationError(
            "OPENAI_TIMEOUT_SECONDS must be a number"
        ) from exc

    try:
        client = OpenAI(api_key=api_key, timeout=timeout)
        response = client.responses.parse(
            model=model,
            instructions=ANALYSIS_INSTRUCTIONS,
            input=build_analysis_input(incident),
            text_format=IncidentAnalysis,
            store=False,
        )
    except OpenAIError as exc:
        raise AnalysisServiceError("OpenAI API request failed") from exc

    analysis = response.output_parsed
    if analysis is None:
        raise AnalysisServiceError("OpenAI API returned no structured analysis")
    return analysis
