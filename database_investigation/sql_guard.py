"""AI生成SQLに対する保守的な読み取り専用検査。"""

from __future__ import annotations

import re

from database_investigation.models import DatabaseQueryPlan


class UnsafeQueryError(Exception):
    """実行を許可できないSQLが含まれている。"""


FORBIDDEN = re.compile(
    r"\b(insert|update|delete|replace|merge|drop|alter|create|truncate|grant|"
    r"revoke|call|execute|prepare|set|load|outfile|dumpfile|lock|unlock)\b",
    re.IGNORECASE,
)
TABLE_REF = re.compile(r"\b(?:from|join)\s+`?([a-zA-Z0-9_]+)`?", re.IGNORECASE)
LIMIT = re.compile(r"\blimit\s+(\d+)\s*$", re.IGNORECASE)
PLACEHOLDER = re.compile(r"%\(([a-zA-Z_][a-zA-Z0-9_]*)\)s")
SELECT_STAR = re.compile(r"\bselect\s+(?:distinct\s+)?(?:[a-zA-Z0-9_]+\.)?\*", re.IGNORECASE)


def validate_query_plan(
    plan: DatabaseQueryPlan,
    allowed: set[str],
    *,
    max_rows: int = 20,
) -> None:
    """全クエリが許可された単一SELECTであることを検証する。"""
    if not allowed:
        raise UnsafeQueryError("No tables are allowed")
    if not plan.rationale.strip() or not 1 <= len(plan.queries) <= 3:
        raise UnsafeQueryError("The query plan must contain one to three queries")
    for query in plan.queries:
        if (
            not query.purpose.strip()
            or not query.dataMinimizationReason.strip()
            or not query.selectedColumns
            or any(not column.strip() for column in query.selectedColumns)
        ):
            raise UnsafeQueryError("Query metadata is incomplete")
        sql = query.sql.strip().rstrip(";").strip()
        if ";" in sql or "--" in sql or "/*" in sql or "#" in sql:
            raise UnsafeQueryError("Multiple statements or comments are not allowed")
        if not re.match(r"^select\b", sql, re.IGNORECASE):
            raise UnsafeQueryError("Only SELECT queries are allowed")
        if FORBIDDEN.search(sql):
            raise UnsafeQueryError("A forbidden SQL keyword was found")
        if SELECT_STAR.search(sql):
            raise UnsafeQueryError("SELECT * is not allowed")
        if not re.search(r"\bwhere\b", sql, re.IGNORECASE):
            raise UnsafeQueryError("A restrictive WHERE clause is required")
        placeholders = set(PLACEHOLDER.findall(sql))
        parameter_names = [parameter.name for parameter in query.parameters]
        if any(
            not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", name)
            for name in parameter_names
        ):
            raise UnsafeQueryError("An invalid SQL parameter name was found")
        if len(parameter_names) != len(set(parameter_names)):
            raise UnsafeQueryError("Duplicate SQL parameters are not allowed")
        if placeholders != set(parameter_names):
            raise UnsafeQueryError("SQL placeholders and parameters do not match")
        tables = {name.lower() for name in TABLE_REF.findall(sql)}
        if not tables or not tables.issubset(allowed):
            raise UnsafeQueryError("The query references a table outside the allowlist")
        limit_match = LIMIT.search(sql)
        if not limit_match or int(limit_match.group(1)) > max_rows:
            raise UnsafeQueryError("LIMIT is missing or exceeds the maximum")
