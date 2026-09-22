"""PR作成要求の検証。"""

import json
from typing import Any

from azure.functions import HttpRequest


class PullRequestValidationError(Exception):
    def __init__(self, message: str):
        self.message = message


def _object(value: Any, name: str) -> dict:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise PullRequestValidationError(f"{name} must be an object") from exc
    if not isinstance(value, dict):
        raise PullRequestValidationError(f"{name} must be an object")
    return value


def parse_pull_request(req: HttpRequest) -> dict:
    try:
        body = req.get_json()
    except ValueError as exc:
        raise PullRequestValidationError("JSON body is required") from exc
    body = _object(body, "body")
    result = {}
    for name in ("incident", "analysis", "databaseInvestigation", "repositoryInvestigation"):
        result[name] = _object(body.get(name), name)
    incident = result["incident"]
    if not str(incident.get("id", "")).strip() or not str(incident.get("title", "")).strip():
        raise PullRequestValidationError("incident.id and incident.title are required")
    investigation = result["repositoryInvestigation"]
    if isinstance(investigation.get("repositoryInvestigation"), dict):
        investigation = investigation["repositoryInvestigation"]
    result["repositoryAssessment"] = _object(investigation, "repositoryInvestigation.repositoryInvestigation")
    return result
