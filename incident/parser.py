"""リクエストの解析とバリデーション。"""

from __future__ import annotations

from typing import Any

from azure.functions import HttpRequest

JSON_CONTENT_TYPE = "application/json"

REQUIRED_FIELDS = ("id", "title", "description")


class ValidationError(Exception):
    """バリデーションエラー。"""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def is_json_content_type(content_type: str | None) -> bool:
    """Content-Type が application/json かどうかを判定する。"""
    if not content_type:
        return False
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type == JSON_CONTENT_TYPE


def parse_incident_request(req: HttpRequest) -> dict[str, Any]:
    """HTTP リクエストから障害情報を解析する。

    Raises:
        ValidationError: バリデーションに失敗した場合。
    """
    if not is_json_content_type(req.headers.get("Content-Type")):
        raise ValidationError("Content-Type は application/json である必要があります")

    try:
        body = req.get_json()
    except ValueError:
        raise ValidationError("リクエストボディは有効な JSON である必要があります") from None

    if not isinstance(body, dict):
        raise ValidationError("リクエストボディは JSON オブジェクトである必要があります")

    for field in REQUIRED_FIELDS:
        if field not in body:
            raise ValidationError(f"必須項目 '{field}' が存在しません")

        value = body[field]
        if not isinstance(value, str):
            raise ValidationError(f"必須項目 '{field}' は文字列である必要があります")

        if value.strip() == "":
            raise ValidationError(f"必須項目 '{field}' は空文字にできません")

    return body
