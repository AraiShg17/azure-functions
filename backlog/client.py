"""Backlog APIクライアント。"""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


class BacklogConfigurationError(Exception):
    """Backlog設定が不足している。"""


class BacklogServiceError(Exception):
    """Backlog API呼び出しに失敗した。"""


def _settings() -> tuple[str, str, str, float]:
    base_url = os.getenv("BACKLOG_BASE_URL", "").strip().rstrip("/")
    api_key = os.getenv("BACKLOG_API_KEY", "").strip()
    project_key = os.getenv("BACKLOG_PROJECT_KEY", "").strip()
    if not all((base_url, api_key, project_key)):
        raise BacklogConfigurationError("Backlog settings are missing")
    try:
        timeout = float(os.getenv("BACKLOG_TIMEOUT_SECONDS", "15"))
    except ValueError as exc:
        raise BacklogConfigurationError("Invalid Backlog timeout") from exc
    return base_url, api_key, project_key, timeout


def _get_json(path: str) -> list[dict]:
    base_url, api_key, _, timeout = _settings()
    request = Request(
        f"{base_url}{path}",
        method="GET",
        headers={"Backlog-API-Key": api_key, "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            value = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise BacklogServiceError("Backlog request failed") from exc
    if not isinstance(value, list):
        raise BacklogServiceError("Unexpected Backlog response")
    return value


def get_issue_types() -> list[dict]:
    """登録先プロジェクトで利用可能な課題種別を取得する。"""
    _, _, project_key, _ = _settings()
    return _get_json(f"/api/v2/projects/{quote(project_key, safe='')}/issueTypes")


def get_priorities() -> list[dict]:
    """利用可能な優先度を取得する。"""
    return _get_json("/api/v2/priorities")


def create_issue(
    summary: str,
    description: str,
    *,
    issue_type_id: int,
    priority_id: int,
) -> dict:
    base_url, api_key, project_key, timeout = _settings()
    data = urlencode({
        "projectId": project_key,
        "summary": summary,
        "description": description,
        "issueTypeId": issue_type_id,
        "priorityId": priority_id,
    }).encode("utf-8")
    request = Request(
        f"{base_url}/api/v2/issues",
        data=data,
        method="POST",
        headers={
            "Backlog-API-Key": api_key,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise BacklogServiceError("Backlog request failed") from exc
