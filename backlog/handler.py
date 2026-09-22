"""Backlog起票HTTPハンドラー。"""

from __future__ import annotations

import json
import logging

from azure.functions import HttpRequest, HttpResponse

from backlog.client import (
    BacklogConfigurationError,
    BacklogServiceError,
    create_issue,
    get_issue_types,
    get_priorities,
    get_project_id,
)
from backlog.formatter import format_backlog_issue
from backlog.parser import BacklogValidationError, parse_backlog_request
from backlog.router import (
    BacklogRoutingConfigurationError,
    BacklogRoutingServiceError,
    select_routing,
)

logger = logging.getLogger(__name__)


def _response(body: dict, status: int) -> HttpResponse:
    return HttpResponse(
        json.dumps(body, ensure_ascii=False, default=str),
        status_code=status,
        mimetype="application/json",
        charset="utf-8",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )


def handle_create_backlog_issue(req: HttpRequest) -> HttpResponse:
    """起票内容をプレビューし、dryRun=falseならBacklogへ登録する。"""
    logger.info("Backlog起票リクエストを受け付けました")
    try:
        data = parse_backlog_request(req)
        summary, description = format_backlog_issue(data)
        routing, issue_type_id, priority_id = select_routing(
            data,
            get_issue_types(),
            get_priorities(),
        )
        if data["dryRun"]:
            logger.info("Backlog起票内容のプレビューを生成しました")
            return _response({
                "success": True,
                "mode": "preview",
                "backlogIssue": {
                    "summary": summary,
                    "description": description,
                    "issueType": routing.issueTypeName,
                    "priority": routing.priorityName,
                    "routingRationale": routing.rationale,
                },
            }, 200)
        issue = create_issue(
            summary,
            description,
            project_id=get_project_id(),
            issue_type_id=issue_type_id,
            priority_id=priority_id,
        )
        logger.info("Backlog課題を作成しました")
        return _response({
            "success": True,
            "mode": "created",
            "backlogIssue": {
                "id": issue.get("id"),
                "issueKey": issue.get("issueKey"),
                "summary": issue.get("summary", summary),
                "issueType": routing.issueTypeName,
                "priority": routing.priorityName,
                "routingRationale": routing.rationale,
            },
        }, 201)
    except BacklogValidationError as exc:
        return _response({"success": False, "message": exc.message}, 400)
    except (BacklogConfigurationError, BacklogRoutingConfigurationError):
        logger.error("Backlog起票が異常終了しました: 設定エラー")
        return _response({"success": False, "message": "Backlogの設定が完了していません"}, 500)
    except BacklogServiceError:
        logger.error("Backlog起票が異常終了しました: APIエラー")
        return _response({"success": False, "message": "Backlogへの課題登録に失敗しました"}, 502)
    except BacklogRoutingServiceError:
        logger.error("Backlog起票が異常終了しました: AI振り分けエラー")
        return _response({"success": False, "message": "課題種別と優先度の判定に失敗しました"}, 502)
    except Exception:
        logger.error("Backlog起票が異常終了しました: 想定外のエラー")
        return _response({"success": False, "message": "内部サーバーエラーが発生しました"}, 500)
