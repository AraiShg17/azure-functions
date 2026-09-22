"""保護対象ブランチに触れず、作業ブランチとPRだけを作成する。"""

import base64
import re
from urllib.parse import quote, urlencode

from repository_investigation.github_client import _settings, api_request
from repository_pull_request.models import PullRequestProposal, PullRequestReview


class UnsafeChangeError(Exception):
    pass


def branch_name(incident_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9-]+", "-", incident_id).strip("-").lower() or "unknown"
    return f"fix/incident-{safe}"


def validate_proposal(proposal: PullRequestProposal, files: list[dict]) -> None:
    allowed = {item["path"] for item in files}
    forbidden = (".github/workflows/", ".git/", ".env", "AGENTS.md", "CLAUDE.md")
    total = 0
    for change in proposal.changes:
        if change.path not in allowed or any(part in change.path for part in forbidden):
            raise UnsafeChangeError("AI proposed a file outside the approved set")
        size = len(change.content.encode("utf-8"))
        if size > 100_000:
            raise UnsafeChangeError("AI proposed an oversized file")
        total += size
    if total > 200_000:
        raise UnsafeChangeError("AI proposed oversized changes")


def create_pull_request(
    incident_id: str,
    proposal: PullRequestProposal,
    review: PullRequestReview,
    files: list[dict],
) -> dict:
    _, owner, repository, base, _ = _settings()
    branch = branch_name(incident_id)
    validate_proposal(proposal, files)
    encoded_head = quote(f"{owner}:{branch}")
    existing = api_request("GET", f"/repos/{quote(owner)}/{quote(repository)}/pulls?" + urlencode({"state": "all", "head": f"{owner}:{branch}"}))
    if isinstance(existing, list) and existing:
        pr = existing[0]
        return {"created": False, "branch": branch, "number": pr["number"], "url": pr["html_url"], "changedFiles": [c.path for c in proposal.changes], "review": review.model_dump()}

    base_ref = api_request("GET", f"/repos/{quote(owner)}/{quote(repository)}/git/ref/heads/{quote(base, safe='')}")
    try:
        api_request("GET", f"/repos/{quote(owner)}/{quote(repository)}/git/ref/heads/{quote(branch, safe='')}")
    except Exception:
        api_request("POST", f"/repos/{quote(owner)}/{quote(repository)}/git/refs", {"ref": f"refs/heads/{branch}", "sha": base_ref["object"]["sha"]})

    file_map = {item["path"]: item for item in files}
    for change in proposal.changes:
        api_request("PUT", f"/repos/{quote(owner)}/{quote(repository)}/contents/{quote(change.path, safe='/')}", {
            "message": f"Fix incident {incident_id}: {change.explanation}"[:250],
            "content": base64.b64encode(change.content.encode("utf-8")).decode("ascii"),
            "branch": branch,
            "sha": file_map[change.path]["sha"],
        })
    pr = api_request("POST", f"/repos/{quote(owner)}/{quote(repository)}/pulls", {
        "title": proposal.title[:256], "head": branch, "base": base,
        "body": proposal.body + "\n\n> AIが生成した修正です。マージ前に人間が確認してください。",
        "draft": True,
    })
    review_body = review.summary
    if review.issues:
        review_body += "\n\n確認事項:\n" + "\n".join(f"- {item}" for item in review.issues)
    review_body += f"\n\n判定: {review.verdict}"
    api_request("POST", f"/repos/{quote(owner)}/{quote(repository)}/pulls/{pr['number']}/reviews", {"body": review_body, "event": "COMMENT"})
    return {"created": True, "branch": branch, "number": pr["number"], "url": pr["html_url"], "changedFiles": [c.path for c in proposal.changes], "review": review.model_dump()}
