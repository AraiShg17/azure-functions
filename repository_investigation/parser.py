"""リポジトリ調査リクエストの解析。"""

from __future__ import annotations

import json
from typing import Any

from azure.functions import HttpRequest


class RepositoryValidationError(Exception):
    def __init__(self, message: str):
        self.message = message


def _object(value: Any, name: str) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise RepositoryValidationError(f"{name} must be an object") from exc
    if not isinstance(value, dict):
        raise RepositoryValidationError(f"{name} must be an object")
    return value


def parse_repository_request(req: HttpRequest) -> dict[str, Any]:
    try:
        body = req.get_json()
    except ValueError as exc:
        raise RepositoryValidationError("Invalid JSON") from exc
    body = _object(body, "body")
    incident = _object(body.get("incident"), "incident")
    for field in ("id", "title", "description"):
        if not isinstance(incident.get(field), str) or not incident[field].strip():
            raise RepositoryValidationError(f"incident.{field} is required")
    body["incident"] = incident
    body["analysis"] = _object(body.get("analysis"), "analysis")
    body["databaseInvestigation"] = _object(
        body.get("databaseInvestigation"), "databaseInvestigation"
    )
    return body
