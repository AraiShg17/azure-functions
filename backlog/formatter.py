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


def _repository_section(repository_work: dict[str, Any] | None) -> str:
    if not repository_work:
        return "## GitHub調査・修正\nGitHub調査は実施されていません。"
    assessment = repository_work.get("repositoryInvestigation") or {}
    pull_request = repository_work.get("pullRequest") or {}
    findings = assessment.get("findings") or []
    finding_text = _lines([
        f"{item.get('file')}:{item.get('line')} - {item.get('finding')}（根拠: {item.get('evidence')}）"
        for item in findings if isinstance(item, dict)
    ])
    if pull_request:
        pr_text = (
            f"- URL: {pull_request.get('url', '')}\n"
            f"- PR番号: #{pull_request.get('number', '')}\n"
            f"- 作業ブランチ: {pull_request.get('branch', '')}\n"
            f"- 変更ファイル:\n{_lines(pull_request.get('changedFiles'))}"
        )
        review = pull_request.get("review") or {}
        review_text = (
            f"**AIレビュー**\n{review.get('summary', '')}\n\n"
            f"**レビュー確認事項**\n{_lines(review.get('issues'))}\n\n"
            f"**レビュー判定**\n{review.get('verdict', '')}"
        )
    else:
        pr_text = f"- PR未作成: {repository_work.get('message', '原因未特定または修正対象なし')}"
        review_text = ""
    return f"""## GitHub調査・修正
**調査結果**
{assessment.get('summary', '')}

**疑われるコード上の原因**
{assessment.get('likelyCause') or '特定できていません。'}

**確認した根拠**
{finding_text}

**推奨変更**
{_lines(assessment.get('recommendedChanges'))}

**確信度**
{assessment.get('confidence', 0)}

**Pull Request**
{pr_text}

{review_text}"""


def format_backlog_issue(payload: dict[str, Any]) -> tuple[str, str]:
    """Backlogの件名と説明を生成する。"""
    incident = payload["incident"]
    analysis = payload["analysis"]
    investigation = payload["databaseInvestigation"]
    plan = investigation.get("queryPlan") or {}
    results = investigation.get("queryResults") or []
    assessment = investigation.get("databaseInvestigation") or {}
    repository_section = _repository_section(payload.get("repositoryWork"))
    simulated = investigation.get("mode") == "simulated"
    if investigation.get("mode") == "skipped":
        source_label = "未実施（一次分析でDB調査不要と判定）"
    elif simulated:
        source_label = "シミュレーション（仮データ。実DBの調査結果ではありません）"
    else:
        source_label = "実DB（読み取り専用接続）"
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

{repository_section}
"""
    return summary, description
