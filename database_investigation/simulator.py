"""DB未接続時に使用する明示的なサンプル結果。"""

from __future__ import annotations

import re
from typing import Any

from database_investigation.models import DatabaseQueryPlan


def _sample_rows(sql: str, query_index: int) -> list[dict[str, Any]]:
    lowered = sql.lower()
    if "customers" in lowered:
        if query_index == 0:
            return [{
                "customer_id": 1001,
                "birth_date": None,
                "status": "active",
                "profile_customer_id": 1001,
                "show_age": True,
                "calculated_age": None,
            }]
        return [
            {
                "customer_id": 1000,
                "birth_date": "1990-04-15",
                "status": "active",
                "profile_customer_id": 1000,
                "show_age": True,
                "calculated_age": 36,
            },
            {
                "customer_id": 1001,
                "birth_date": None,
                "status": "active",
                "profile_customer_id": 1001,
                "show_age": True,
                "calculated_age": None,
            },
        ]
    if re.search(r"\bpages\b", lowered):
        return [{
            "page_id": 501,
            "path": "/sample-page",
            "publish_status": "draft",
            "published_at": None,
            "deleted_at": None,
        }]
    if re.search(r"\borders\b", lowered):
        return [{
            "order_id": 9001,
            "customer_id": 1001,
            "status": "failed",
            "total_amount": "4500.00",
        }]
    if "audit_logs" in lowered:
        return []
    return []


def simulate_plan(plan: DatabaseQueryPlan) -> list[dict[str, Any]]:
    """SQLごとにサンプル行を返す。実DBへは接続しない。"""
    results = []
    for index, query in enumerate(plan.queries):
        rows = _sample_rows(query.sql, index)
        results.append({
            "purpose": query.purpose,
            "selectedColumns": query.selectedColumns,
            "rowCount": len(rows),
            "rows": rows,
            "simulated": True,
        })
    return results
