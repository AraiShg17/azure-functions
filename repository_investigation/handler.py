"""リポジトリ調査HTTPハンドラー。"""

from __future__ import annotations

import json
import logging

from azure.functions import HttpRequest, HttpResponse

from repository_investigation.assessor import (
    RepositoryAssessmentConfigurationError,
    RepositoryAssessmentServiceError,
    assess_repository,
)
from repository_investigation.github_client import (
    GitHubConfigurationError,
    GitHubServiceError,
    search_and_fetch,
)
from repository_investigation.parser import (
    RepositoryValidationError,
    parse_repository_request,
)
from repository_investigation.planner import (
    RepositoryPlanningConfigurationError,
    RepositoryPlanningServiceError,
    create_search_plan,
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


def handle_investigate_repository(req: HttpRequest) -> HttpResponse:
    logger.info("リポジトリ調査リクエストを受け付けました")
    try:
        data = parse_repository_request(req)
        plan = create_search_plan(data)
        inspected_files, snippets = search_and_fetch(plan.searchTerms)
        assessment = assess_repository(data, plan, snippets)
        logger.info("リポジトリ調査が正常に完了しました")
        return _response({
            "success": True,
            "limits": {
                "maxSearchTerms": 8,
                "maxFiles": 15,
                "maxFileBytes": 100000,
                "maxTotalBytes": 500000,
                "maxSnippets": 20,
            },
            "searchPlan": plan.model_dump(),
            "inspectedFiles": inspected_files,
            "codeSnippets": [
                {key: value for key, value in snippet.items() if key != "content"}
                for snippet in snippets
            ],
            "repositoryInvestigation": assessment.model_dump(),
        }, 200)
    except RepositoryValidationError as exc:
        return _response({"success": False, "message": exc.message}, 400)
    except (
        GitHubConfigurationError,
        RepositoryPlanningConfigurationError,
        RepositoryAssessmentConfigurationError,
    ):
        logger.error("リポジトリ調査が異常終了しました: 設定エラー")
        return _response({"success": False, "message": "リポジトリ調査の設定が完了していません"}, 500)
    except GitHubServiceError:
        logger.error("リポジトリ調査が異常終了しました: GitHub APIエラー")
        return _response({"success": False, "message": "GitHubからのコード取得に失敗しました"}, 502)
    except (RepositoryPlanningServiceError, RepositoryAssessmentServiceError):
        logger.error("リポジトリ調査が異常終了しました: AIエラー")
        return _response({"success": False, "message": "リポジトリのAI調査に失敗しました"}, 502)
    except Exception:
        logger.error("リポジトリ調査が異常終了しました: 想定外のエラー")
        return _response({"success": False, "message": "内部サーバーエラーが発生しました"}, 500)
