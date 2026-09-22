"""DB調査HTTPリクエストの解析。"""

from __future__ import annotations

from typing import Any

from azure.functions import HttpRequest


class InvestigationValidationError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def parse_investigation_request(req: HttpRequest) -> dict[str, Any]:
    content_type = req.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise InvestigationValidationError("Content-Typeはapplication/jsonにしてください")
    try:
        data = req.get_json()
    except (ValueError, TypeError):
        raise InvestigationValidationError("リクエストボディをJSONとして解析できません") from None
    if not isinstance(data, dict):
        raise InvestigationValidationError("リクエストボディはJSONオブジェクトにしてください")
    incident = data.get("incident")
    analysis = data.get("analysis")
    if not isinstance(incident, dict) or not isinstance(analysis, dict):
        raise InvestigationValidationError("incidentとanalysisは必須です")
    for field in ("id", "title", "description"):
        if not isinstance(incident.get(field), str) or not incident[field].strip():
            raise InvestigationValidationError(f"incident.{field}は空でない文字列にしてください")
    questions = analysis.get("databaseQuestions")
    if not isinstance(questions, list) or not questions or not all(
        isinstance(item, str) and item.strip() for item in questions
    ):
        raise InvestigationValidationError("analysis.databaseQuestionsは空でない文字列配列にしてください")
    execute = data.get("execute", False)
    if not isinstance(execute, bool):
        raise InvestigationValidationError("executeはbooleanにしてください")
    return {"incident": incident, "questions": questions, "execute": execute}
