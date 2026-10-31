#!/usr/bin/env python3
"""Виявити змінені шляхи, спільні з ранішими відкритими GitHub PR.

Запити до API лише на читання: GraphQL query та REST GET. Це перевірка перетину шляхів, а не CLAIM,
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
    except error.HTTPError as exc:
        # Точний HTTP-код потрібен для діагностики 403/404/429;
        # не виводимо URL, тіло відповіді, заголовки чи токен.
        raise AuditError(f"GitHub REST файли PR: HTTP {exc.code}") from None
    except (error.URLError, TimeoutError, ValueError, OSError) as exc:
        raise AuditError(
            f"GitHub REST недоступний або повернув невірний JSON ({type(exc).__name__})"
        ) from None


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
        if isinstance(item, dict):
            names = [item.get("filename")]
            if item.get("status") == "renamed":
                # GitHub повідомляє обидва шляхи: конфлікт можливий і зі
                # старою назвою, і з новою. Відсутність старої — помилка API.
                names.append(item.get("previous_filename"))
        else:
            names = [item]
        for name in names:
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



# У PullRequestChangedFile немає previous_filename: для перейменувань
# робимо точковий REST-запит, а не втрачаємо попередній шлях.
GRAPHQL_QUERY = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(first: 100, after: $cursor, states: OPEN) {
      nodes {
        number
        files(first: 100) {
          totalCount
          nodes { path changeType }
          pageInfo { hasNextPage }
        }
      }
      pageInfo { hasNextPage endCursor }
    }
  }
}
"""
GRAPHQL_PR_PAGES = 10
PATCH_STATUSES = {"ADDED", "CHANGED", "COPIED", "DELETED", "MODIFIED", "RENAMED"}


def get_graphql(query: str, variables: dict, token: str) -> object:
    """Один запит GraphQL без права мутації; не друкувати токен."""
    req = request.Request(
        API + "/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "ukrainian-books-pr-overlap-audit"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=20) as reply:
            return json.load(reply)
    except (error.HTTPError, error.URLError, TimeoutError, ValueError, OSError) as exc:
        code = f" HTTP {exc.code}" if isinstance(exc, error.HTTPError) else ""
        raise AuditError(
            f"GitHub GraphQL недоступний або повернув невірний JSON"
            f" ({type(exc).__name__}{code})"
        ) from None


def read_live_graphql(repo: str, pr_number: int, graphql_fetch, rest_fetch) -> list[dict]:
    """Прочитати всі відкриті PR кількома GraphQL сторінками.

    Замість десятків REST-запитів використовуємо GraphQL-з'єднання файлів;
    для перейменувань і >100 змінених файлів обов'язковий повний REST fallback.
    Неповна пагінація, помилки API чи невідомі поля — fail-closed.
    """
    if not REPO.fullmatch(repo):
        raise AuditError("Назва репозиторію має формат owner/repo")
    owner, name = repo.split("/")
    cursor = None
    records: list[dict] = []
    seen: set[int] = set()
    for _ in range(GRAPHQL_PR_PAGES):
        payload = graphql_fetch(GRAPHQL_QUERY, {
            "owner": owner, "name": name, "cursor": cursor,
        })
        if not isinstance(payload, dict) or payload.get("errors"):
            raise AuditError("Часткова або помилкова відповідь GitHub GraphQL")
        data = payload.get("data")
        repository = data.get("repository") if isinstance(data, dict) else None
        connection = repository.get("pullRequests") if isinstance(repository, dict) else None
        if not isinstance(connection, dict) or not isinstance(connection.get("nodes"), list):
            raise AuditError("Неповний список відкритих PR у GraphQL")
        for pr in connection["nodes"]:
            if not isinstance(pr, dict):
                raise AuditError("Некоректний PR у GraphQL")
            number = pr.get("number")
            if type(number) is not int or number <= 0 or number in seen:
                raise AuditError("Некоректний або повторений номер PR у GraphQL")
            seen.add(number)
            if number > pr_number:
                continue
            files = pr.get("files")
            if not isinstance(files, dict):
                raise AuditError("Відсутній список змінених файлів у GraphQL")
            nodes, total = files.get("nodes"), files.get("totalCount")
            page_info = files.get("pageInfo")
            if (not isinstance(nodes, list) or type(total) is not int
                    or total < 0 or not isinstance(page_info, dict)
                    or type(page_info.get("hasNextPage")) is not bool):
                raise AuditError("Неповний перелік змінених файлів у GraphQL")
            converted = []
            fallback = total > 100 or page_info["hasNextPage"]
            for file in nodes:
                if not isinstance(file, dict):
                    raise AuditError("Некоректний файл PR у GraphQL")
                path, change = file.get("path"), file.get("changeType")
                if (not isinstance(path, str) or not path.strip()
                        or type(change) is not str or change not in PATCH_STATUSES):
                    raise AuditError("Некоректний шлях або тип зміни в GraphQL")
                converted.append({"filename": path})
                if change == "RENAMED":
                    fallback = True
            if fallback:
                converted = pages(f"/repos/{repo}/pulls/{number}/files", rest_fetch)
            if len(converted) != total:
                raise AuditError("Неповний або змінений перелік файлів PR")
            # Валідність REST fallback перевіряємо одразу, зокрема
            # обов'язковий previous_filename для перейменувань.
            file_paths(converted)
            records.append({"number": number, "files": converted})
        page = connection.get("pageInfo")
        if (not isinstance(page, dict)
                or type(page.get("hasNextPage")) is not bool):
            raise AuditError("Немає ознаки завершення пагінації GraphQL")
        if not page["hasNextPage"]:
            if pr_number not in seen:
                raise AuditError(f"PR #{pr_number} відсутній серед відкритих")
            return records
        next_cursor = page.get("endCursor")
        if not isinstance(next_cursor, str) or not next_cursor or next_cursor == cursor:
            raise AuditError("Невірний курсор пагінації GraphQL")
        cursor = next_cursor
    raise AuditError("Перевищено межу сторінок GraphQL: результат неповний")


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
            records = read_live_graphql(
                args.repo, args.pr,
                lambda query, vars_: get_graphql(query, vars_, token),
                lambda path: get_json(path, token),
            )
        return run(args.pr, records, args.strict)
    except (AuditError, OSError, ValueError) as exc:
        print(f"КООРД-ПОМИЛКА: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
