"""HTTP レスポンスの生成。"""

from __future__ import annotations

import json
from typing import Any

from azure.functions import HttpResponse

from incident.models import IncidentAnalysis

RESPONSE_CONTENT_TYPE = "application/json; charset=utf-8"


def _json_response(body: dict[str, Any], status_code: int) -> HttpResponse:
    """JSON レスポンスを生成する。"""
    return HttpResponse(
        body=json.dumps(body, ensure_ascii=False),
        status_code=status_code,
        headers={"Content-Type": RESPONSE_CONTENT_TYPE},
        mimetype="application/json",
        charset="utf-8",
    )


def success_response(
    incident: dict[str, Any],
    analysis: IncidentAnalysis,
) -> HttpResponse:
    """正常時のレスポンスを生成する。"""
    return _json_response(
        {
            "success": True,
            "message": "障害情報を受信しました",
            "incident": {
                "id": incident["id"],
                "title": incident["title"],
                "category": incident.get("category"),
            },
            "analysis": analysis.to_response_dict(),
        },
        status_code=200,
    )


def error_response(message: str, status_code: int) -> HttpResponse:
    """エラー時のレスポンスを生成する。"""
    return _json_response(
        {
            "success": False,
            "message": message,
        },
        status_code=status_code,
    )
