"""障害情報受信の HTTP ハンドラー。"""

from __future__ import annotations

import logging

from azure.functions import HttpRequest, HttpResponse

from incident.analyzer import (
    AnalysisConfigurationError,
    AnalysisServiceError,
    analyze_incident,
)
from incident.parser import ValidationError, parse_incident_request
from incident.response import error_response, success_response

logger = logging.getLogger(__name__)


def handle_receive_incident(req: HttpRequest) -> HttpResponse:
    """障害情報受信リクエストを処理する。"""
    logger.info("障害情報の受信リクエストを受け付けました")

    try:
        incident = parse_incident_request(req)
        logger.info("SharePoint項目ID: %s", incident["id"])
        logger.info("タイトル: %s", incident["title"])

        analysis = analyze_incident(incident)
        response = success_response(incident, analysis)
        logger.info("障害情報の受信が正常に完了しました")
        return response

    except ValidationError as exc:
        logger.warning("障害情報の受信が異常終了しました: %s", exc.message)
        return error_response(exc.message, status_code=400)

    except AnalysisConfigurationError:
        logger.error("障害情報の受信が異常終了しました: AI設定エラー")
        return error_response("AI分析の設定が完了していません", status_code=500)

    except AnalysisServiceError:
        logger.error("障害情報の受信が異常終了しました: AI分析エラー")
        return error_response("AI分析に失敗しました", status_code=502)

    except Exception:
        # 例外メッセージにも description が含まれる可能性があるため記録しない。
        logger.error("障害情報の受信が異常終了しました: 想定外のエラー")
        return error_response("内部サーバーエラーが発生しました", status_code=500)
