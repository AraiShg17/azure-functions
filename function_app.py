"""Azure Functions アプリケーションエントリポイント。"""

import azure.functions as func

from incident.handler import handle_receive_incident

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.route(route="receive_incident", methods=["POST"])
def receive_incident(req: func.HttpRequest) -> func.HttpResponse:
    """SharePoint 障害一覧からの HTTP POST を受信する。"""
    return handle_receive_incident(req)