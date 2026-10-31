#!/usr/bin/env python3
"""УКР-07: ретроспективний доказовий аудит GitHub Reviews злитих PR.

Цей звіт лише описує наявні записи GitHub, а не визначає юридичну,
академічну чи людську незалежність рецензента і не санкціонує merge.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import sys
from urllib.request import Request, urlopen

API = "https://api.github.com"
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA = re.compile(r"^[a-fA-F0-9]{40}$")
DECISIONS = {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}


def time_value(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result if result.tzinfo is not None else None
    except ValueError:
        return None


def inspect(pr: dict, reviews: list[dict] | None) -> dict:
    """Не змішувати наявність GitHub APPROVED із незалежною рецензією."""
    number = pr.get("number")
    head = (pr.get("head") or {}).get("sha")
    author = (pr.get("user") or {}).get("login")
    merged_at = time_value(pr.get("merged_at"))
    result = {
        "pr": number, "head_sha": head, "merged_at": pr.get("merged_at"),
        "status": "insufficient_data", "github_approvals_on_head": [],
    }
    if reviews is None or not isinstance(reviews, list):
        result["reason"] = "Не отримано повного списку GitHub Reviews"
        return result
    if (not isinstance(head, str) or not SHA.fullmatch(head)
            or not isinstance(author, str) or not author.strip()
            or merged_at is None):
        result["reason"] = "Неповні реквізити автора, SHA або дати злиття"
        return result

    # Лише останнє ДО злиття рішення кожного GitHub-акаунта.
    # COMMENTED та PENDING не скасовують ранішу рецензію.
    latest: dict[str, tuple[datetime, int, dict]] = {}
    ambiguous = False
    for item in reviews:
        if not isinstance(item, dict):
            ambiguous = True
            continue
        state = item.get("state")
        if state not in DECISIONS:
            continue
        login = (item.get("user") or {}).get("login")
        submitted = time_value(item.get("submitted_at"))
        if not isinstance(login, str) or not login or submitted is None:
            ambiguous = True
            continue
        if submitted > merged_at:
            continue
        key = login.casefold()
        ident = item.get("id")
        serial = ident if isinstance(ident, int) else 0
        ranking = (submitted, serial)
        if key not in latest or ranking > latest[key][:2]:
            latest[key] = (submitted, serial, item)

    matched = []
    for login, (_, _, review) in latest.items():
        if (login != author.casefold()
                and review.get("state") == "APPROVED"
                and review.get("commit_id") == head):
            matched.append((review.get("user") or {}).get("login") or login)
    result["github_approvals_on_head"] = sorted(matched, key=str.casefold)
    if matched:
        result["status"] = "github_approval_observed"
        result["reason"] = ("Є GitHub APPROVED від іншого акаунта до merge "
                            "на точному head SHA; незалежність особи не встановлена")
    elif ambiguous:
        result["status"] = "insufficient_data"
        result["reason"] = "Деякі рішення GitHub Reviews мають неповні реквізити"
    else:
        result["status"] = "no_verifiable_github_approval"
        result["reason"] = ("Немає доказу GitHub APPROVED іншого акаунта "
                            "до merge на точному head SHA")
    return result


def audit(pulls: list[dict], reviews_by_number: dict, limit: int) -> dict:
    rows = []
    for pr in pulls:
        if not isinstance(pr, dict) or not pr.get("merged_at"):
            continue
        if len(rows) >= limit:
            break
        key = str(pr.get("number"))
        rows.append(inspect(pr, reviews_by_number.get(key)))
    return {
        "scope": ("Ретроспективні GitHub Reviews; НЕ доказ незалежності людини, "
                  "правового дозволу, санскритологічної рецензії або захисту main"),
        "audited_merged_prs": len(rows),
        "github_approval_observed": sum(r["status"] == "github_approval_observed" for r in rows),
        "no_verifiable_github_approval": sum(
            r["status"] == "no_verifiable_github_approval" for r in rows),
        "insufficient_data": sum(r["status"] == "insufficient_data" for r in rows),
        "results": rows,
    }


def get_json(path: str, token: str | None) -> object:
    headers = {"Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request(API + path, headers=headers, method="GET")
    with urlopen(request, timeout=20) as response:
        return json.load(response)


def pages(path: str, token: str | None, max_pages: int = 10) -> list:
    data: list = []
    for page in range(1, max_pages + 1):
        join = "&" if "?" in path else "?"
        rows = get_json(path + join + "per_page=100&page=" + str(page), token)
        if not isinstance(rows, list):
            raise ValueError("GitHub API не повернув список записів")
        data.extend(rows)
        if len(rows) < 100:
            return data
    raise ValueError("Забагато сторінок API: відмовлено від неповного звіту")


def live(repo: str, limit: int, token: str | None) -> dict:
    if not REPO.fullmatch(repo):
        raise ValueError("Репозиторій має формат власник/назва")
    closed: list[dict] = []
    for page in range(1, 11):
        path = ("/repos/" + repo + "/pulls?state=closed&sort=updated"
                "&direction=desc&per_page=100&page=" + str(page))
        data = get_json(path, token)
        if not isinstance(data, list):
            raise ValueError("GitHub API не повернув список PR")
        closed.extend(p for p in data if isinstance(p, dict) and p.get("merged_at"))
        if len(closed) >= limit or len(data) < 100:
            break
    else:
        raise ValueError("Не вдалося охопити потрібну кількість злитих PR")
    reviews: dict[str, list] = {}
    for pr in closed[:limit]:
        n = pr.get("number")
        if type(n) is not int or n < 1:
            raise ValueError("Злитий PR не має коректного номера")
        reviews[str(n)] = pages("/repos/" + repo + "/pulls/" + str(n) + "/reviews", token)
    return audit(closed, reviews, limit)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="juv4uk/ukrainian-books")
    parser.add_argument("--fixture", type=Path, help="офлайн JSON з pulls і reviews")
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args()
    if not 1 <= args.limit <= 100:
        parser.error("--limit має бути від 1 до 100")
    try:
        if args.fixture:
            data = json.loads(args.fixture.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not isinstance(data.get("pulls"), list) \
                    or not isinstance(data.get("reviews"), dict):
                raise ValueError("fixture мусить мати pulls:[] та reviews:{}")
            output = audit(data["pulls"], data["reviews"], args.limit)
        else:
            output = live(args.repo, args.limit,
                          os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN"))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("ПОМИЛКА звіту: " + str(exc), file=sys.stderr)
        return 1
    print(json.dumps(output, ensure_ascii=False, indent=2) )
    # Історичні незареєстровані approval не повинні валити сьогоднішній PR.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
