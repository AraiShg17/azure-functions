"""安全な作業ブランチに修正をコミットしてPRを作成するHTTPハンドラー。"""

import json
import logging

from azure.functions import HttpRequest, HttpResponse

from repository_investigation.github_client import (
    GitHubConfigurationError,
    GitHubServiceError,
    fetch_files,
    search_and_fetch,
)
from repository_investigation.assessor import (
    RepositoryAssessmentConfigurationError,
    RepositoryAssessmentServiceError,
    assess_repository,
)
from repository_investigation.planner import (
    RepositoryPlanningConfigurationError,
    RepositoryPlanningServiceError,
    create_search_plan,
)
from repository_pull_request.github_writer import UnsafeChangeError, create_pull_request
from repository_pull_request.parser import PullRequestValidationError, parse_pull_request
from repository_pull_request.proposer import (
    ProposalConfigurationError,
    ProposalServiceError,
    propose_changes,
    review_changes,
)

logger = logging.getLogger(__name__)


def _response(body: dict, status: int) -> HttpResponse:
    return HttpResponse(
        json.dumps(body, ensure_ascii=False, default=str), status_code=status,
        mimetype="application/json", charset="utf-8",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )


def handle_create_repository_pull_request(req: HttpRequest) -> HttpResponse:
    logger.info("リポジトリ修正PR作成リクエストを受け付けました")
    try:
        data = parse_pull_request(req)
        plan = create_search_plan(data)
        inspected_files, snippets = search_and_fetch(plan.searchTerms)
        assessment_model = assess_repository(data, plan, snippets)
        assessment = assessment_model.model_dump()
        data["repositoryAssessment"] = assessment
        if assessment_model.problemIdentified is not True:
            return _response({
                "success": False, "created": False,
                "message": "原因が特定されていないためPRを作成しません",
                "repositoryInvestigation": assessment,
            }, 422)
        paths = ["AGENTS.md"]
        paths += [item.get("file", "") for item in assessment.get("findings", []) if isinstance(item, dict)]
        paths += inspected_files
        files = fetch_files([path for path in paths if path])
        editable = [item for item in files if item["path"] != "AGENTS.md"]
        if not editable:
            return _response({"success": False, "created": False, "message": "修正対象の既存ファイルを取得できませんでした"}, 422)
        proposal = propose_changes(data, files)
        review = review_changes(data, proposal)
        result = create_pull_request(str(data["incident"]["id"]), proposal, review, editable)
        logger.info("リポジトリ修正PRの処理が正常に完了しました")
        return _response({
            "success": True,
            "mode": "created" if result["created"] else "existing",
            "repositoryInvestigation": assessment,
            "pullRequest": result,
        }, 201 if result["created"] else 200)
    except PullRequestValidationError as exc:
        return _response({"success": False, "message": exc.message}, 400)
    except UnsafeChangeError:
        return _response({"success": False, "message": "AIの修正案が安全制約を満たしません"}, 422)
    except (
        GitHubConfigurationError,
        ProposalConfigurationError,
        RepositoryPlanningConfigurationError,
        RepositoryAssessmentConfigurationError,
    ):
        logger.error("PR作成が異常終了しました: 設定エラー")
        return _response({"success": False, "message": "PR作成の設定が完了していません"}, 500)
    except GitHubServiceError:
        logger.error("PR作成が異常終了しました: GitHub APIエラー")
        return _response({"success": False, "message": "GitHubへのPR作成に失敗しました"}, 502)
    except (ProposalServiceError, RepositoryPlanningServiceError, RepositoryAssessmentServiceError):
        logger.error("PR作成が異常終了しました: AIエラー")
        return _response({"success": False, "message": "AIによる修正またはレビューに失敗しました"}, 502)
    except Exception:
        logger.exception("PR作成が異常終了しました")
        return _response({"success": False, "message": "内部サーバーエラーが発生しました"}, 500)
