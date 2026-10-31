#!/usr/bin/env python3
"""Звіт про спостережувані бар'єри рецензування відкритих PR (без дозволу на merge)."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API = "https://api.github.com"
GOOD = {"success"}  # skipped/neutral не доводять, що потрібна перевірка відбулась
STATES = {"APPROVED", "CHANGES_REQUESTED", "COMMENTED", "DISMISSED", "PENDING"}
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def fetch_json(path: str, token: str | None = None) -> dict | list:
    """Тільки GET до фіксованого GitHub API, без надсилання приватних даних у звіт."""
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(API + path, headers=headers, method="GET")
    with urlopen(request, timeout=20) as resp:
        return json.load(resp)


def fetch_pages(path: str, token: str | None = None) -> list:
    out = []
    for page in range(1, 51):
        sep = "&" if "?" in path else "?"
        payload = fetch_json(f"{path}{sep}per_page=100&page={page}", token)
        if not isinstance(payload, list):
            raise ValueError(f"Очікувався список від GitHub: {path}")
        out.extend(payload)
        if len(payload) < 100:
            return out
    raise ValueError("Пагінація перевищила 5000 записів: звіт може бути неповним")


def snapshot(repo: str, token: str | None = None) -> list[dict]:
    if not REPO_RE.fullmatch(repo):
        raise ValueError("Репозиторій має бути в форматі owner/name")
    prs = fetch_pages(f"/repos/{repo}/pulls?state=open", token)
    result = []
    for pr in prs:
        n = pr["number"]
        sha = pr["head"]["sha"]
        reviews = fetch_pages(f"/repos/{repo}/pulls/{n}/reviews", token)
        check_data = fetch_json(f"/repos/{repo}/commits/{sha}/check-runs?per_page=100", token)
        if not isinstance(check_data, dict) or not isinstance(check_data.get("check_runs"), list):
            raise ValueError(f"GitHub не повернув check-runs для PR #{n}")
        if check_data.get("total_count", 0) > 100:
            raise ValueError(f"PR #{n}: понад 100 перевірок, потрібна пагінація")
        result.append({"pr": pr, "reviews": reviews, "checks": check_data["check_runs"]})
    return result


def inspect(entry: dict) -> dict:
    """Стан PR у момент зняття даних; ніколи не є дозволом на злиття."""
    pr = entry["pr"]
    number = pr["number"]
    head = pr["head"]["sha"]
    author = pr["user"]["login"].casefold()
    last = {}
    for review in entry.get("reviews", []):
        user = (review.get("user") or {}).get("login")
        if not isinstance(user, str) or user.casefold() == author:
            continue
        state = review.get("state", "")
        if state in STATES:
            last[user.casefold()] = review
    approvals = sorted(u for u, v in last.items()
                       if v.get("state") == "APPROVED" and v.get("commit_id") == head)
    stale = sorted(u for u, v in last.items()
                   if v.get("state") == "APPROVED" and v.get("commit_id") != head)
    requested = sorted(u for u, v in last.items() if v.get("state") == "CHANGES_REQUESTED")
    checks = entry.get("checks", [])
    failed = sorted(str(c.get("name", "без назви")) for c in checks
                    if c.get("conclusion") in {"failure", "timed_out", "cancelled", "action_required"})
    unfinished = sorted(str(c.get("name", "без назви")) for c in checks
                        if c.get("status") != "completed" or c.get("conclusion") not in GOOD)
    issues = []
    if pr.get("draft"):
        issues.append("чернетка")
    if not approvals:
        issues.append("немає актуального схвалення іншою особою")
    if stale:
        issues.append("є схвалення на попередньому SHA")
    if requested:
        issues.append("є чинний запит змін")
    if not checks:
        issues.append("не знайдено CI на SHA; не означає, що його немає на merge SHA")
    elif unfinished:
        issues.append("не всі спостережені перевірки успішні")
    return {
        "number": number,
        "title": pr.get("title", ""),
        "url": pr.get("html_url", ""),
        "head_sha": head,
        "draft": bool(pr.get("draft")),
        "approvals_current_sha": approvals,
        "approvals_stale_sha": stale,
        "changes_requested": requested,
        "checks_observed": len(checks),
        "checks_failed": failed,
        "checks_unverified": unfinished,
        "observed_technical_blockers": issues,
        "manual_requirements": [
            "окрема перевірка прав і походження",
            "філологічне та редакторське рецензування за характером внеску",
            "перевірка обов'язкових checks і актуальності main безпосередньо перед merge",
        ],
        "automatically_mergeable": False,
    }


def report(entries: list[dict]) -> dict:
    rows = [inspect(x) for x in entries]
    rows.sort(key=lambda x: x["number"])
    return {
        "kind": "спостереження, не дозвіл на злиття",
        "count": len(rows),
        "drafts": sum(x["draft"] for x in rows),
        "without_current_independent_approval": sum(not x["approvals_current_sha"] for x in rows),
        "checks_unknown_or_unverified": sum(not x["checks_observed"] or x["checks_unverified"] != [] for x in rows),
        "pull_requests": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="juv4uk/ukrainian-books", help="owner/name")
    parser.add_argument("--fixture", help="Офлайн JSON: список {pr, reviews, checks}, без мережі")
    args = parser.parse_args()
    try:
        if args.fixture:
            with open(args.fixture, encoding="utf-8") as handle:
                entries = json.load(handle)
            if not isinstance(entries, list):
                raise ValueError("Офлайн-набір має бути списком")
        else:
            entries = snapshot(args.repo, os.environ.get("GITHUB_TOKEN"))
        print(json.dumps(report(entries), ensure_ascii=False, indent=2))
    except (HTTPError, URLError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ПОМИЛКА аудиту: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
