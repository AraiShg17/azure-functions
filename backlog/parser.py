"""Backlog起票リクエストの解析。"""

from __future__ import annotations

import json
from typing import Any

from azure.functions import HttpRequest


class BacklogValidationError(Exception):
    def __init__(self, message: str):
        self.message = message


def _object(value: Any, name: str) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise BacklogValidationError(f"{name} must be an object") from exc
    if not isinstance(value, dict):
        raise BacklogValidationError(f"{name} must be an object")
    return value


def parse_backlog_request(req: HttpRequest) -> dict[str, Any]:
    try:
        body = req.get_json()
    except ValueError as exc:
        raise BacklogValidationError("Invalid JSON") from exc
    body = _object(body, "body")
    incident = _object(body.get("incident"), "incident")
    for field in ("id", "title", "description"):
        if not isinstance(incident.get(field), str) or not incident[field].strip():
            raise BacklogValidationError(f"incident.{field} is required")
    body["incident"] = incident
    body["analysis"] = _object(body.get("analysis"), "analysis")
    investigation = _object(body.get("databaseInvestigation"), "databaseInvestigation")
    body["databaseInvestigation"] = investigation
    _object(investigation.get("queryPlan"), "databaseInvestigation.queryPlan")
    if not isinstance(investigation.get("queryResults"), list):
        raise BacklogValidationError("databaseInvestigation.queryResults must be an array")
    _object(
        investigation.get("databaseInvestigation"),
        "databaseInvestigation.databaseInvestigation",
    )
    repository_work = body.get("repositoryWork")
    if repository_work is not None:
        body["repositoryWork"] = _object(repository_work, "repositoryWork")
    dry_run = body.get("dryRun", True)
    if not isinstance(dry_run, bool):
        raise BacklogValidationError("dryRun must be a boolean")
    body["dryRun"] = dry_run
    return body
