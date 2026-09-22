"""DB未接続時のサンプル結果テスト。"""

from database_investigation.models import (
    DatabaseQuery,
    DatabaseQueryParameter,
    DatabaseQueryPlan,
)
from database_investigation.simulator import simulate_plan


def test_customer_query_returns_explicitly_simulated_rows() -> None:
    plan = DatabaseQueryPlan(
        rationale="顧客を確認する",
        queries=[DatabaseQuery(
            purpose="生年月日を確認する",
            selectedColumns=["customer_id", "birth_date"],
            dataMinimizationReason="必要な列だけ取得する",
            sql="SELECT customer_id, birth_date FROM customers WHERE customer_id=%(id)s LIMIT 1",
            parameters=[DatabaseQueryParameter(name="id", value="1001")],
        )],
    )
    results = simulate_plan(plan)
    assert results[0]["simulated"] is True
    assert results[0]["rowCount"] == 1
    assert results[0]["rows"][0]["birth_date"] is None
