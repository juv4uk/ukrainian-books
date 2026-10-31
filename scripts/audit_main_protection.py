#!/usr/bin/env python3
"""Інформаційний аудит стану захисту гілки GitHub без зміни налаштувань."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def get_json(url: str, token: str = ""):
    """Читає лише відкриті метадані; помилки передає виклику."""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ukrainian-books-main-protection-audit",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urlopen(Request(url, headers=headers), timeout=15) as response:
        return json.load(response)


def summarize(branch_data, rulesets_data, branch_error=None, rulesets_error=None):
    """Не виводить фальшивого схвалення рецензій чи status checks."""
    protected = (
        branch_data.get("protected")
        if isinstance(branch_data, dict)
        and type(branch_data.get("protected")) is bool
        else None
    )
    active = None
    if isinstance(rulesets_data, list):
        active = sorted(
            x["name"] for x in rulesets_data
            if isinstance(x, dict) and x.get("enforcement") == "active"
            and isinstance(x.get("name"), str)
        )
    return {
        "стан": ("захищено" if protected is True else
                 "незахищено" if protected is False else "невідомо"),
        "protected": protected,
        "активні_rulesets": active,
        "рев'ю_підтверджено": False,
        "обов'язкові_CI_підтверджено": False,
        "заборону_force_push_підтверджено": False,
        "похибка_читання_гілки": branch_error,
        "похибка_читання_rulesets": rulesets_error,
        "попередження": (
            "Поле protected не доводить налаштування конкретних перевірок "
            "чи незалежного рецензування. Це тільки інформаційний аудит."
        ),
    }


def inspect(repo: str, branch: str = "main", token: str = "", fetch=get_json):
    base = f"https://api.github.com/repos/{repo}"
    branch_data = None
    rulesets_data = None
    branch_error = None
    rulesets_error = None
    try:
        branch_data = fetch(f"{base}/branches/{branch}", token)
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
        branch_error = type(exc).__name__
    try:
        rulesets_data = fetch(f"{base}/rulesets", token)
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
        rulesets_error = type(exc).__name__
    return summarize(branch_data, rulesets_data, branch_error, rulesets_error)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=os.getenv(
        "GITHUB_REPOSITORY", "juv4uk/ukrainian-books"))
    parser.add_argument("--branch", default="main")
    parser.add_argument("--report", default="reports/branch-protection.json")
    parser.add_argument(
        "--require-protected", action="store_true",
        help="Повертати код 2, якщо protected не є строго true")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repo):
        parser.error("Очікується owner/repository")
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", args.branch):
        parser.error("Недійсна назва гілки")
    result = inspect(args.repo, args.branch, os.getenv("GITHUB_TOKEN", ""))
    result["репозиторій"] = args.repo
    result["гілка"] = args.branch
    output = Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if args.require_protected and result["protected"] is not True else 0


if __name__ == "__main__":
    sys.exit(main())
