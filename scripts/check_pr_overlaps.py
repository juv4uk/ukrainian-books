#!/usr/bin/env python3
"""Виявити змінені шляхи, спільні з ранішими відкритими GitHub PR.

Читання API — тільки через GET. Це перевірка перетину шляхів, а не CLAIM,
академічна рецензія чи автоматична підстава для злиття.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib import error, request

API = "https://api.github.com"
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
PAGE_SIZE = 100
MAX_PAGES = 30  # GitHub обмежує перелік файлів PR 3000 записами.


class AuditError(Exception):
    """Стан не можна надійно перевірити; зелений результат заборонений."""


def get_json(path: str, token: str) -> object:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ukrainian-books-pr-overlap-audit",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = request.Request(API + path, headers=headers)
    try:
        with request.urlopen(req, timeout=15) as reply:
            return json.load(reply)
    except (error.HTTPError, error.URLError, TimeoutError, ValueError, OSError) as exc:
        # Не друкуємо URL/заголовки запиту чи токен з винятку.
        raise AuditError(f"GitHub API недоступне або повернуло невірний JSON ({type(exc).__name__})") from None


def pages(endpoint: str, fetch, max_pages: int = MAX_PAGES) -> list[dict]:
    result: list[dict] = []
    for page in range(1, max_pages + 1):
        separator = "&" if "?" in endpoint else "?"
        payload = fetch(f"{endpoint}{separator}per_page={PAGE_SIZE}&page={page}")
        if not isinstance(payload, list) or any(not isinstance(x, dict) for x in payload):
            raise AuditError("Некоректний перелік у відповіді GitHub API")
        result.extend(payload)
        if len(payload) < PAGE_SIZE:
            return result
    raise AuditError("Перевищено межу сторінок GitHub API: результат неповний")


def file_paths(items: object) -> set[str]:
    if not isinstance(items, list):
        raise AuditError("Список файлів PR має бути масивом")
    paths: set[str] = set()
    for item in items:
        name = item.get("filename") if isinstance(item, dict) else item
        if not isinstance(name, str) or not name.strip() or any(c in name for c in "\r\n\0"):
            raise AuditError("Відповідь PR містить некоректний шлях файла")
        paths.add(name)
    return paths


def overlaps(pr_number: int, records: object) -> list[dict]:
    """Лише раніші відкриті PR, точний збіг файла; більший номер — новіший."""
    if not isinstance(records, list):
        raise AuditError("Невірний список відкритих PR")
    opened: dict[int, set[str]] = {}
    for item in records:
        if not isinstance(item, dict) or type(item.get("number")) is not int:
            raise AuditError("Відповідь містить PR без цілого номера")
        number = item["number"]
        if number <= 0 or number in opened:
            raise AuditError("Некоректний або повторений номер PR")
        opened[number] = file_paths(item.get("files"))
    if pr_number not in opened:
        raise AuditError(f"PR #{pr_number} відсутній у переліку відкритих PR")
    ours = opened[pr_number]
    return [
        {"pr": number, "paths": sorted(ours & paths)}
        for number, paths in sorted(opened.items())
        if number < pr_number and ours & paths
    ]


def read_live(repo: str, pr_number: int, fetch) -> list[dict]:
    if not REPO.fullmatch(repo):
        raise AuditError("Назва репозиторію має формат owner/repo")
    base = f"/repos/{repo}"
    opened = pages(f"{base}/pulls?state=open", fetch, max_pages=10)
    numbers: set[int] = set()
    for item in opened:
        n = item.get("number")
        if type(n) is not int or n in numbers:
            raise AuditError("Некоректні або повторені номери в API")
        numbers.add(n)
    if pr_number not in numbers:
        raise AuditError(f"PR #{pr_number} не знайдено серед відкритих")
    records = []
    for number in sorted(n for n in numbers if n <= pr_number):
        data = pages(f"{base}/pulls/{number}/files", fetch)
        records.append({"number": number, "files": data})
    return records


def run(pr_number: int, records: object, strict: bool) -> int:
    collisions = overlaps(pr_number, records)
    result = {"pr": pr_number, "status": "conflict" if collisions else "ok", "overlaps": collisions}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if strict and collisions else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--pr", type=int, required=True, help="Номер відкритого PR")
    parser.add_argument("--strict", action="store_true", help="Завершити з кодом 1 за перетину")
    parser.add_argument("--snapshot", type=Path, help="Офлайновий JSON: {'pulls': [{'number': N, 'files': [...]}]}")
    args = parser.parse_args()
    try:
        if args.pr <= 0:
            raise AuditError("Номер PR має бути додатним")
        if args.snapshot:
            data = json.loads(args.snapshot.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise AuditError("Некоректна структура snapshot")
            records = data.get("pulls")
        else:
            token = os.environ.get("GITHUB_TOKEN", "")
            if not token:
                raise AuditError("GITHUB_TOKEN відсутній: мережевий аудит не виконано")
            records = read_live(args.repo, args.pr, lambda path: get_json(path, token))
        return run(args.pr, records, args.strict)
    except (AuditError, OSError, ValueError) as exc:
        print(f"КООРД-ПОМИЛКА: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
