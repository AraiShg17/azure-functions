"""Azure Functions アプリケーションエントリポイント。"""

import azure.functions as func

from incident.handler import handle_receive_incident
from database_investigation.handler import handle_investigate_database
from backlog.handler import handle_create_backlog_issue

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.route(route="receive_incident", methods=["POST"])
def receive_incident(req: func.HttpRequest) -> func.HttpResponse:
    """SharePoint 障害一覧からの HTTP POST を受信する。"""
    return handle_receive_incident(req)


@app.route(route="investigate_database", methods=["POST"])
def investigate_database(req: func.HttpRequest) -> func.HttpResponse:
    """一次分析結果からDB調査計画を作成し、必要に応じて実行する。"""
    return handle_investigate_database(req)


@app.route(route="create_backlog_issue", methods=["POST"])
def create_backlog_issue(req: func.HttpRequest) -> func.HttpResponse:
    """障害調査結果を整形し、必要に応じてBacklogへ起票する。"""
    return handle_create_backlog_issue(req)
