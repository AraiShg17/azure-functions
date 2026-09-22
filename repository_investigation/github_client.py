"""取得量を制限したGitHubコード検索クライアント。"""

from __future__ import annotations

import base64
import json
import os
from pathlib import PurePosixPath
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


class GitHubConfigurationError(Exception):
    pass


class GitHubServiceError(Exception):
    pass


EXCLUDED_PARTS = {
    ".git", "node_modules", "vendor", "dist", "build", "coverage",
    ".next", "target", "generated", "__pycache__",
}
EXCLUDED_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".pdf", ".zip",
    ".gz", ".mp4", ".mov", ".woff", ".woff2", ".ttf", ".map", ".lock",
}


def _settings() -> tuple[str, str, str, str, float]:
    token = os.getenv("GITHUB_TOKEN", "").strip()
    owner = os.getenv("GITHUB_OWNER", "").strip()
    repository = os.getenv("GITHUB_REPOSITORY", "").strip()
    branch = os.getenv("GITHUB_BASE_BRANCH", "main").strip()
    if not all((token, owner, repository, branch)):
        raise GitHubConfigurationError("GitHub settings are missing")
    try:
        timeout = float(os.getenv("GITHUB_TIMEOUT_SECONDS", "15"))
    except ValueError as exc:
        raise GitHubConfigurationError("Invalid GitHub timeout") from exc
    return token, owner, repository, branch, timeout


def _request(path: str) -> dict[str, Any]:
    token, _, _, _, timeout = _settings()
    request = Request(
        f"https://api.github.com{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "incident-investigation-function",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            value = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise GitHubServiceError("GitHub request failed") from exc
    if not isinstance(value, dict):
        raise GitHubServiceError("Unexpected GitHub response")
    return value


def _allowed_path(path: str) -> bool:
    pure = PurePosixPath(path)
    return not (set(pure.parts) & EXCLUDED_PARTS) and pure.suffix.lower() not in EXCLUDED_SUFFIXES


def search_and_fetch(terms: list[str]) -> tuple[list[str], list[dict[str, Any]]]:
    """最大15ファイル、各100KB、合計500KBから最大20断片を返す。"""
    _, owner, repository, branch, _ = _settings()
    paths: list[str] = []
    for term in terms[:8]:
        query = f"{term} repo:{owner}/{repository}"
        params = urlencode({"q": query, "per_page": 10})
        result = _request(f"/search/code?{params}")
        for item in result.get("items", []):
            path = item.get("path", "")
            if path and _allowed_path(path) and path not in paths:
                paths.append(path)
            if len(paths) >= 15:
                break
        if len(paths) >= 15:
            break

    snippets: list[dict[str, Any]] = []
    total_bytes = 0
    for path in paths:
        encoded_path = quote(path, safe="/")
        params = urlencode({"ref": branch})
        result = _request(
            f"/repos/{quote(owner)}/{quote(repository)}/contents/{encoded_path}?{params}"
        )
        if result.get("encoding") != "base64" or not isinstance(result.get("content"), str):
            continue
        try:
            raw = base64.b64decode(result["content"], validate=False)
            text = raw.decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            continue
        if len(raw) > 100_000 or total_bytes + len(raw) > 500_000:
            continue
        total_bytes += len(raw)
        lines = text.splitlines()
        matching = [
            index for index, line in enumerate(lines)
            if any(term.casefold() in line.casefold() for term in terms)
        ]
        if not matching:
            continue
        center = matching[0]
        start = max(0, center - 40)
        end = min(len(lines), center + 41)
        snippets.append({
            "path": path,
            "startLine": start + 1,
            "endLine": end,
            "content": "\n".join(lines[start:end]),
        })
        if len(snippets) >= 20:
            break
    return paths, snippets
