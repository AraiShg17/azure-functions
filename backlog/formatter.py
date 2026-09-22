"""障害調査結果をBacklogの課題本文へ整形する。"""

from __future__ import annotations

import json
from typing import Any


def _lines(values: list[Any] | None, empty: str = "なし") -> str:
    if not values:
        return f"- {empty}"
    return "\n".join(f"- {value}" for value in values)


def _query_sections(plan: dict[str, Any], results: list[dict[str, Any]]) -> str:
    sections: list[str] = []
    for index, query in enumerate(plan.get("queries") or [], start=1):
        result = results[index - 1] if index <= len(results) else {}
        parameters = query.get("parameters") or []
        parameter_text = _lines(
            [f"{item.get('name')}: {item.get('value')}" for item in parameters]
        )
        rows = result.get("rows") or []
        rows_text = json.dumps(rows, ensure_ascii=False, indent=2, default=str)
        sections.append(
            f"### SQL {index}\n"
            f"**目的**\n{query.get('purpose', '')}\n\n"
            f"**取得項目**\n{_lines(query.get('selectedColumns'))}\n\n"
            f"**必要最小限にした理由**\n{query.get('dataMinimizationReason', '')}\n\n"
            f"**SQL**\n```sql\n{query.get('sql', '')}\n```\n\n"
            f"**パラメータ**\n{parameter_text}\n\n"
            f"**取得件数**\n{result.get('rowCount', 0)}件\n\n"
            f"**取得データ**\n```json\n{rows_text}\n```"
        )
    return "\n\n".join(sections) if sections else "SQLは生成されていません。"


def format_backlog_issue(payload: dict[str, Any]) -> tuple[str, str]:
    """Backlogの件名と説明を生成する。"""
    incident = payload["incident"]
    analysis = payload["analysis"]
    investigation = payload["databaseInvestigation"]
    plan = investigation.get("queryPlan") or {}
    results = investigation.get("queryResults") or []
    assessment = investigation.get("databaseInvestigation") or {}
    simulated = investigation.get("mode") == "simulated"
    source_label = (
        "シミュレーション（仮データ。実DBの調査結果ではありません）"
        if simulated else "実DB（読み取り専用接続）"
    )
    summary = f"[障害調査] {incident['title']}"
    description = f"""## 起票された課題
- SharePoint項目ID: {incident['id']}
- タイトル: {incident['title']}
- 本文: {incident['description']}

## AIによる一次分析
**想定された状況**
{analysis.get('summary', '')}

**DBで確認すべき事項**
{_lines(analysis.get('databaseQuestions'))}

**リポジトリで確認すべき事項**
{_lines(analysis.get('repositoryQuestions'))}

## DB調査
- データ種別: {source_label}
- SQL生成理由: {plan.get('rationale', '')}

{_query_sections(plan, results)}

## 調査結果
**考察**
{assessment.get('summary', '')}

**疑われる原因**
{assessment.get('likelyCause') or '現時点では特定できていません。'}

**根拠**
{_lines(assessment.get('evidence'))}

**問題を特定できたか**
{'はい' if assessment.get('problemIdentified') else 'いいえ'}

**追加のリポジトリ調査が必要か**
{'はい' if assessment.get('needsRepositoryInvestigation') else 'いいえ'}

**推奨対応**
{_lines(assessment.get('recommendedActions'))}

**確信度**
{assessment.get('confidence', 0)}
"""
    return summary, description
