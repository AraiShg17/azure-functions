"""読み取り専用MySQL接続による調査SQL実行。"""

from __future__ import annotations

import os
from typing import Any

import pymysql

from database_investigation.models import DatabaseQueryPlan


class DatabaseConfigurationError(Exception):
    """DB接続設定が不足または危険である。"""


class DatabaseExecutionError(Exception):
    """DB調査の実行に失敗した。"""


def _setting(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise DatabaseConfigurationError(f"{name} is missing")
    return value


def execute_plan(plan: DatabaseQueryPlan) -> list[dict[str, Any]]:
    """読み取り専用トランザクションで計画を実行する。"""
    user = _setting("DB_USER")
    if user.lower() in {"root", "admin", "administrator"}:
        raise DatabaseConfigurationError("A privileged DB user is not allowed")
    try:
        port = int(os.getenv("DB_PORT", "3306"))
        timeout = int(os.getenv("DB_TIMEOUT_SECONDS", "10"))
    except ValueError as exc:
        raise DatabaseConfigurationError("Invalid numeric DB setting") from exc

    try:
        connection = pymysql.connect(
            host=_setting("DB_HOST"),
            port=port,
            user=user,
            password=_setting("DB_PASSWORD"),
            database=_setting("DB_NAME"),
            connect_timeout=timeout,
            read_timeout=timeout,
            write_timeout=timeout,
            autocommit=False,
            cursorclass=pymysql.cursors.DictCursor,
            ssl={"ssl": {}} if os.getenv("DB_SSL", "true").lower() == "true" else None,
        )
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("SET SESSION TRANSACTION READ ONLY")
                cursor.execute("START TRANSACTION READ ONLY")
                results = []
                for query in plan.queries:
                    cursor.execute(query.sql, query.parameters)
                    results.append({
                        "purpose": query.purpose,
                        "rows": list(cursor.fetchall()),
                    })
                connection.rollback()
                return results
    except DatabaseConfigurationError:
        raise
    except Exception as exc:
        raise DatabaseExecutionError("Database query failed") from exc
