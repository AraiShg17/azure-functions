"""ローカルのスキーマ文書を検索する簡易RAG。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

RAG_DATA_PATH = Path(__file__).parent.parent / "rag_data" / "database_schema.json"


def _terms(text: str) -> set[str]:
    latin = re.findall(r"[a-zA-Z0-9_]{2,}", text.lower())
    japanese = re.findall(r"[一-龥ぁ-んァ-ヶー]{2,}", text)
    return set(latin + japanese)


def load_chunks(path: Path = RAG_DATA_PATH) -> list[dict[str, Any]]:
    """RAG用チャンクを読み込む。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("RAG data must be an array")
    return data


def retrieve_schema_context(
    search_text: str,
    *,
    limit: int = 4,
    path: Path = RAG_DATA_PATH,
) -> list[dict[str, Any]]:
    """質問とのキーワード一致度が高いスキーマチャンクを返す。"""
    query_terms = _terms(search_text)
    scored: list[tuple[int, int, dict[str, Any]]] = []
    for index, chunk in enumerate(load_chunks(path)):
        haystack = " ".join(
            [chunk.get("title", ""), chunk.get("content", "")]
            + list(chunk.get("keywords", []))
        )
        score = len(query_terms & _terms(haystack))
        for keyword in chunk.get("keywords", []):
            if keyword.lower() in search_text.lower():
                score += 3
        scored.append((score, -index, chunk))

    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    matches = [item[2] for item in scored if item[0] > 0][:limit]
    return matches or [item[2] for item in scored[:1]]


def allowed_tables(chunks: list[dict[str, Any]]) -> set[str]:
    """取得チャンクに記載された参照許可テーブルを集約する。"""
    return {
        table.lower()
        for chunk in chunks
        for table in chunk.get("allowedTables", [])
    }
