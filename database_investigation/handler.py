"""DB調査HTTPハンドラー。"""

from __future__ import annotations

import json
import logging
import os

from azure.functions import HttpRequest, HttpResponse

from database_investigation.assessor import (
    AssessmentConfigurationError,
    AssessmentServiceError,
    assess_database_results,
)

from database_investigation.executor import (
    DatabaseConfigurationError,
    DatabaseExecutionError,
    execute_plan,
)
from database_investigation.parser import (
    InvestigationValidationError,
    parse_investigation_request,
)
from database_investigation.planner import (
    PlanningConfigurationError,
    PlanningServiceError,
    create_query_plan,
)
from database_investigation.rag import allowed_tables, retrieve_schema_context
from database_investigation.sql_guard import UnsafeQueryError, validate_query_plan
from database_investigation.simulator import simulate_plan

logger = logging.getLogger(__name__)


def _response(body: dict, status: int) -> HttpResponse:
    return HttpResponse(
        json.dumps(body, ensure_ascii=False, default=str),
        status_code=status,
        mimetype="application/json",
        charset="utf-8",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )


def handle_investigate_database(req: HttpRequest) -> HttpResponse:
    """RAG、SQL計画、安全性検査、任意のDB実行を行う。"""
    logger.info("DB調査リクエストを受け付けました")
    try:
        data = parse_investigation_request(req)
        incident = data["incident"]
        logger.info("SharePoint項目ID: %s", incident["id"])
        logger.info("タイトル: %s", incident["title"])
        search_text = " ".join(
            [incident["title"], incident["description"], *data["questions"]]
        )
        context = retrieve_schema_context(search_text)
        plan = create_query_plan(incident, data["questions"], context)
        tables = allowed_tables(context)
        try:
            max_rows = int(os.getenv("DB_MAX_ROWS", "20"))
        except ValueError as exc:
            raise DatabaseConfigurationError("Invalid DB_MAX_ROWS") from exc
        if not 1 <= max_rows <= 100:
            raise DatabaseConfigurationError("DB_MAX_ROWS must be between 1 and 100")
        validate_query_plan(plan, tables, max_rows=max_rows)
        simulated = not data["execute"]
        results = simulate_plan(plan) if simulated else execute_plan(plan)
        assessment = assess_database_results(
            incident,
            data["questions"],
            context,
            plan,
            results,
            simulated=simulated,
        )
        logger.info("DB調査が正常に完了しました")
        return _response({
            "success": True,
            "mode": "simulated" if simulated else "executed",
            "dataSource": "sampleData" if simulated else "database",
            "retrievedContextIds": [chunk["id"] for chunk in context],
            "allowedTables": sorted(tables),
            "maxRowsPerQuery": max_rows,
            "queryPlan": plan.to_response_dict(),
            "queryResults": results,
            "databaseInvestigation": assessment.to_response_dict(),
        }, 200)
    except InvestigationValidationError as exc:
        logger.warning("DB調査が異常終了しました: 入力エラー")
        return _response({"success": False, "message": exc.message}, 400)
    except (
        PlanningConfigurationError,
        AssessmentConfigurationError,
        DatabaseConfigurationError,
    ):
        logger.error("DB調査が異常終了しました: 設定エラー")
        return _response({"success": False, "message": "DB調査の設定が完了していません"}, 500)
    except PlanningServiceError:
        logger.error("DB調査が異常終了しました: AIエラー")
        return _response({"success": False, "message": "DB調査計画の生成に失敗しました"}, 502)
    except AssessmentServiceError:
        logger.error("DB調査が異常終了しました: DB結果精査AIエラー")
        return _response({"success": False, "message": "DB調査結果の精査に失敗しました"}, 502)
    except UnsafeQueryError:
        logger.error("DB調査が異常終了しました: SQL安全性検査エラー")
        return _response({"success": False, "message": "安全でないSQL計画を拒否しました"}, 422)
    except DatabaseExecutionError:
        logger.error("DB調査が異常終了しました: DB実行エラー")
        return _response({"success": False, "message": "DBからのデータ取得に失敗しました"}, 502)
    except Exception:
        logger.error("DB調査が異常終了しました: 想定外のエラー")
        return _response({"success": False, "message": "内部サーバーエラーが発生しました"}, 500)
