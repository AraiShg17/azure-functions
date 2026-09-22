"""Backlog APIクライアント。"""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class BacklogConfigurationError(Exception):
    """Backlog設定が不足している。"""


class BacklogServiceError(Exception):
    """Backlog API呼び出しに失敗した。"""


def create_issue(summary: str, description: str) -> dict:
    base_url = os.getenv("BACKLOG_BASE_URL", "").strip().rstrip("/")
    api_key = os.getenv("BACKLOG_API_KEY", "").strip()
    project_id = os.getenv("BACKLOG_PROJECT_ID", "").strip()
    issue_type_id = os.getenv("BACKLOG_ISSUE_TYPE_ID", "").strip()
    priority_id = os.getenv("BACKLOG_PRIORITY_ID", "").strip()
    if not all((base_url, api_key, project_id, issue_type_id, priority_id)):
        raise BacklogConfigurationError("Backlog settings are missing")
    try:
        timeout = float(os.getenv("BACKLOG_TIMEOUT_SECONDS", "15"))
    except ValueError as exc:
        raise BacklogConfigurationError("Invalid Backlog timeout") from exc
    data = urlencode({
        "projectId": project_id,
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
