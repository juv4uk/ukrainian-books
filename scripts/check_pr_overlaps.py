#!/usr/bin/env python3
"""Виявити змінені шляхи, спільні з ранішими відкритими GitHub PR.

Запити до API лише на читання: один пакетний GraphQL query та, за потреби,
REST GET. Це перевірка перетину шляхів, а не CLAIM, академічна рецензія чи
автоматична підстава для злиття.

Економіка запитів
----------------
Старий шлях робив один запит на перелік відкритих PR і далі по одному
``/pulls/{n}/files`` на кожен раніший PR — на 107 відкритих PR це 109
запитів. Тепер усі відкриті PR і їхні файли приходять пакетним GraphQL
запитом: один запит на кожні 100 відкритих PR, тобто 1–2 запити на весь
аудит. REST лишається тільки як **точковий** fallback для тих PR, де
GraphQL не дає повної картини: перейменування (у ``PullRequestChangedFile``
немає ``previous_filename``), понад 100 змінених файлів або незавершена
пагінація файлів.

Діагностика збоїв
-----------------
При будь-якому збої друкуємо тип винятку, HTTP-статус, URL, заголовки
лімітів (``X-RateLimit-Remaining``, ``X-RateLimit-Reset``, ``Retry-After``)
і перші 200 символів тіла відповіді. Токен не друкується ні повністю, ні
частково: заголовки запиту не виводяться ніколи, а тіло й адреса додатково
проходять через редагування, якщо сервер раптом відлунить отриманий
``Bearer`` назад у тексті.

Три стани розрізняються навмисно:

* 429 або 403 із ознаками ліміту — стан інфраструктури GitHub, не дефект PR.
  Перевірка спершу чекає (з повагою до ``Retry-After`` і
  ``X-RateLimit-Reset``), а якщо ліміт не минув — голосно позначає
  «ПРОПУЩЕНО» з причиною й повертає код 2: неперевірений аудит не може бути успішним.
* 401 або 403 без ознак ліміту — дефект конфігурації: токен недійсний або
  без прав. Це червоне з названою причиною (код 2).
* мережа, таймаут, 5xx — теж не провина PR: позначаємо як пропущене,
  але обов'язкова перевірка завершується з кодом 2.

Пропуск — це **не** зелений результат: у JSON пишеться ``"status":
"skipped"`` і причина, а код завершення 2 блокує злиття, доки
живу перевірку не буде виконано. Відсутність перетину не вигадується.

Fail-closed (обов'язковий гейт)
-------------------------------
Інфраструктурний пропуск теж блокує злиття (код 2). Червоними
також лишаються: невалідний JSON, ``errors`` у відповіді GraphQL, часткові дані
(менше файлів, ніж оголошено), порожній перелік PR при наявних відкритих PR,
неповна пагінація, розбіжність ``changedFiles`` і ``files.totalCount``,
некоректні шляхи чи типи змін, відсутній PR і, звісно, сам перетин шляхів.
Кожен шлях, де даних немає, веде до коду 2, а не до мовчазного «перетинів
немає».
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request

API = "https://api.github.com"
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
PAGE_SIZE = 100
MAX_PAGES = 30  # GitHub обмежує перелік файлів PR 3000 записами.

TIMEOUT = 20
BODY_LIMIT = 200
RATE_HEADERS = ("X-RateLimit-Remaining", "X-RateLimit-Reset", "Retry-After")
MAX_SINGLE_WAIT = 60.0  # секунд на одну паузу
DEFAULT_MAX_WAIT = 45.0  # секунд на всі паузи одного запуску
MAX_ATTEMPTS = 3  # спроб на один запит: нульовий Retry-After не має зациклити

# Скільки символів токена вважаємо достатніми, щоб витерти й частковий слід.
SECRET_FRAGMENT = 12
# «Bearer abc…» у тілі відповіді — теж привід витерти хвіст.
BEARER = re.compile(r"(?i)\b(bearer)\s+\S+")


class AuditError(Exception):
    """Стан не можна надійно перевірити; зелений результат заборонений."""


class TokenError(AuditError):
    """Токен недійсний або без прав: це дефект конфігурації, а не PR."""


class AuditSkipped(Exception):
    """Інфраструктурна умова (ліміт, мережа, 5xx): не дефект PR.

    Збірку блокує кодом 2 і не оголошує перетин відсутнім: результат
    позначається як ПРОПУЩЕНО з названою причиною.
    """


class Failure:
    """Результат класифікації збою: вид причини і готова діагностика."""

    __slots__ = ("url", "kind", "diagnostic")

    def __init__(self, url: str, kind: str, diagnostic: str) -> None:
        self.url = url
        self.kind = kind  # "limit" | "token" | "network" | "invalid"
        self.diagnostic = diagnostic


def redact(text: str, secret: str) -> str:
    """Витерти токен і його впізнаваний початок/кінець із будь-якого тексту."""
    if not isinstance(text, str):
        return ""
    if secret:
        fragments = {secret}
        if len(secret) >= SECRET_FRAGMENT:
            fragments.add(secret[:SECRET_FRAGMENT])
            fragments.add(secret[-SECRET_FRAGMENT:])
        for fragment in fragments:
            text = text.replace(fragment, "(приховано)")
    return BEARER.sub(r"\1 (приховано)", text)


def _response(exc: BaseException):
    return getattr(exc, "response", None)


def _status(exc: BaseException) -> int | None:
    status = getattr(_response(exc), "status_code", None)
    if status is None:
        status = getattr(exc, "code", None)
    return status if type(status) is int else None


def _headers(exc: BaseException):
    headers = getattr(_response(exc), "headers", None)
    if headers is None:
        headers = getattr(exc, "headers", None)
    return headers if headers is not None else {}


def _body(exc: BaseException) -> str:
    response = _response(exc)
    stream = response if response is not None else exc
    read = getattr(stream, "read", None)
    if read is None:
        return ""
    try:
        raw = read()
    except Exception:  # тіло могло бути прочитане раніше
        return ""
    if isinstance(raw, bytes):
        return raw.decode("utf-8", "replace")
    return raw if isinstance(raw, str) else ""


def reset_moment(headers) -> str | None:
    """Час скидання ліміту з X-RateLimit-Reset у зрозумілому вигляді."""
    try:
        moment = int(headers.get("X-RateLimit-Reset"))
    except (TypeError, ValueError):
        return None
    try:
        return datetime.fromtimestamp(moment, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    except (OverflowError, OSError, ValueError):
        return None


def describe(exc: BaseException, url: str, secret: str = "") -> Failure:
    """Класифікувати збій і скласти діагностику без токена й без заголовків запиту."""
    status = _status(exc)
    headers = _headers(exc)
    body = _body(exc)
    text = redact(body.strip().replace("\r", " ").replace("\n", " ")[:BODY_LIMIT], secret)

    parts = [f"тип={type(exc).__name__}"]
    parts.append(f"HTTP={status}" if status is not None else "HTTP=(немає відповіді)")
    parts.append(f"URL={redact(url, secret)}")
    for name in RATE_HEADERS:
        value = headers.get(name)
        if value not in (None, ""):
            parts.append(f"{name}={redact(str(value), secret)}")
    moment = reset_moment(headers)
    if moment:
        parts.append(f"скинеться={moment}")
    parts.append(f"тіло={text!r}" if text else "тіло=(порожнє)")
    diagnostic = "; ".join(parts)

    low = body.lower()
    remaining = str(headers.get("X-RateLimit-Remaining", "")).strip()
    retry_after = headers.get("Retry-After")
    limit_signals = (
        "rate limit" in low
        or "abuse" in low
        or "secondary rate" in low
        or retry_after not in (None, "")
        or remaining == "0"
    )

    if status == 429:
        return Failure(url, "limit", diagnostic)
    if status == 403 and limit_signals:
        return Failure(url, "limit", diagnostic)
    if status in (401, 403):
        return Failure(url, "token", diagnostic)
    if status is not None and 500 <= status < 600:
        return Failure(url, "network", diagnostic)
    if isinstance(exc, ValueError):
        return Failure(url, "invalid", diagnostic)
    return Failure(url, "network", diagnostic)


def wait_seconds(exc: BaseException, waited: float, max_wait: float) -> float | None:
    """Скільки чекати перед повторною спробою; None — бюджет вичерпано."""
    headers = _headers(exc)
    delay = None
    raw_retry = headers.get("Retry-After")
    if raw_retry not in (None, ""):
        try:
            delay = float(raw_retry)
        except (TypeError, ValueError):
            delay = None
    if delay is None:
        moment = reset_moment(headers)
        if moment:
            try:
                stamp = int(headers.get("X-RateLimit-Reset"))
                delay = stamp - datetime.now(timezone.utc).timestamp()
            except (TypeError, ValueError):
                delay = None
    if delay is None:
        delay = 1.0 + waited  # 1, 2, 4, ... с
    delay = max(0.0, min(float(delay), MAX_SINGLE_WAIT))
    if waited + delay > max_wait:
        return None
    return delay


def request_json(
    url: str,
    token: str = "",
    *,
    body: dict | None = None,
    opener=request.urlopen,
    sleep=time.sleep,
    max_wait: float = DEFAULT_MAX_WAIT,
) -> object:
    """Один логічний запит до GitHub API з класифікацією збоїв і без токена у виводі.

    ``body`` заданий — це POST (GraphQL), інакше GET (REST). Повторюємо лише
    збої ліміту, і лише в межах ``max_wait``.
    """
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ukrainian-books-pr-overlap-audit",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = None
    method = "GET"
    if body is not None:
        headers["Content-Type"] = "application/json"
        payload = json.dumps(body).encode("utf-8")
        method = "POST"
    waited = 0.0
    for attempt in range(1, MAX_ATTEMPTS + 1):
        req = request.Request(url, data=payload, headers=headers, method=method)
        try:
            with opener(req, timeout=TIMEOUT) as reply:
                return json.load(reply)
        except (error.HTTPError, error.URLError, TimeoutError, ValueError, OSError) as exc:
            failure = describe(exc, url, token)
            if failure.kind == "token":
                raise TokenError(
                    "Токен недійсний або без прав (401/403 без ознак ліміту). "
                    + failure.diagnostic
                ) from None
            if failure.kind == "invalid":
                raise AuditError(
                    "Невалідний JSON у відповіді GitHub API. " + failure.diagnostic
                ) from None
            if failure.kind == "network":
                raise AuditSkipped(
                    "ПРОПУЩЕНО: мережа або сервер GitHub недоступні (не провина PR). "
                    + failure.diagnostic
                ) from None
            delay = wait_seconds(exc, waited, max_wait)
            if delay is None or attempt == MAX_ATTEMPTS:
                moment = reset_moment(_headers(exc)) or "час скидання невідомий"
                raise AuditSkipped(
                    f"ПРОПУЩЕНО: ліміт запитів GitHub, скинеться о {moment}. "
                    + failure.diagnostic
                ) from None
            sleep(delay)
            waited += delay
    raise AuditSkipped("ПРОПУЩЕНО: ліміт запитів GitHub не минув за відведений час.")


def get_json(
    path: str,
    token: str,
    *,
    opener=request.urlopen,
    sleep=time.sleep,
    max_wait: float = DEFAULT_MAX_WAIT,
) -> object:
    """REST GET (лише читання): перелік відкритих PR і файли окремих PR."""
    return request_json(
        API + path, token, opener=opener, sleep=sleep, max_wait=max_wait
    )


# У PullRequestChangedFile немає previous_filename: для перейменувань
# робимо точковий REST-запит, а не втрачаємо попередній шлях.
# changedFiles дає незалежну звірку з files.totalCount: якщо API віддасть
# усічений перелік файлів, розбіжність стане помилкою, а не тихим пропуском.
GRAPHQL_QUERY = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(first: 100, after: $cursor, states: OPEN) {
      totalCount
      nodes {
        number
        changedFiles
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
GRAPHQL_FILE_LIMIT = 100
PATCH_STATUSES = {"ADDED", "CHANGED", "COPIED", "DELETED", "MODIFIED", "RENAMED"}


def get_graphql(
    query: str,
    variables: dict,
    token: str,
    *,
    opener=request.urlopen,
    sleep=time.sleep,
    max_wait: float = DEFAULT_MAX_WAIT,
) -> object:
    """Один запит GraphQL без права мутації; не друкувати токен."""
    return request_json(
        API + "/graphql",
        token,
        body={"query": query, "variables": variables},
        opener=opener,
        sleep=sleep,
        max_wait=max_wait,
    )


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


def graphql_connection(payload: object) -> dict:
    """Дістати з'єднання pullRequests; будь-яка неповнота — червоне."""
    if not isinstance(payload, dict):
        raise AuditError("Відповідь GitHub GraphQL має бути об'єктом")
    errors = payload.get("errors")
    if errors:
        # Часткова відповідь із errors — саме той випадок, коли «даних немає»,
        # а зелений результат був би брехнею.
        first = ""
        if isinstance(errors, list) and errors and isinstance(errors[0], dict):
            first = str(errors[0].get("message", ""))[:BODY_LIMIT]
        raise AuditError(
            "GraphQL повернув errors: " + (first if first else "без тексту")
        )
    data = payload.get("data")
    repository = data.get("repository") if isinstance(data, dict) else None
    connection = repository.get("pullRequests") if isinstance(repository, dict) else None
    if not isinstance(connection, dict) or not isinstance(connection.get("nodes"), list):
        raise AuditError("Неповний список відкритих PR у GraphQL")
    return connection


def graphql_files(repo: str, pr: dict, rest_fetch) -> list[dict]:
    """Файли одного PR із GraphQL; перейменування й обрізання — через REST."""
    number = pr["number"]
    files = pr.get("files")
    if not isinstance(files, dict):
        raise AuditError("Відсутній список змінених файлів у GraphQL")
    nodes, total = files.get("nodes"), files.get("totalCount")
    page_info = files.get("pageInfo")
    if (not isinstance(nodes, list) or type(total) is not int or total < 0
            or not isinstance(page_info, dict)
            or type(page_info.get("hasNextPage")) is not bool):
        raise AuditError("Неповний перелік змінених файлів у GraphQL")
    changed = pr.get("changedFiles")
    if type(changed) is not int or changed < 0:
        raise AuditError("Немає кількості змінених файлів PR у GraphQL")
    if changed != total:
        # Дві незалежні цифри з API розійшлися: переліку файлів довіряти не можна.
        raise AuditError(
            f"Кількість змінених файлів PR #{number} не збігається з переліком у GraphQL"
        )
    converted: list[dict] = []
    fallback = total > GRAPHQL_FILE_LIMIT or page_info["hasNextPage"]
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
    return converted


def read_live_graphql(repo: str, pr_number: int, graphql_fetch, rest_fetch) -> list[dict]:
    """Прочитати всі відкриті PR пакетним GraphQL-запитом (1 запит на 100 PR).

    REST зачіпаємо лише точково — для перейменувань і PR із понад 100 файлами.
    Кожен шлях, де даних бракує, веде до ``AuditError``: неповна пагінація,
    ``errors``, розбіжність лічильників, невідомі поля, відсутній PR.
    """
    if not REPO.fullmatch(repo):
        raise AuditError("Назва репозиторію має формат owner/repo")
    owner, name = repo.split("/")
    cursor = None
    records: list[dict] = []
    seen: set[int] = set()
    total_open = 0
    for _ in range(GRAPHQL_PR_PAGES):
        payload = graphql_fetch(GRAPHQL_QUERY, {
            "owner": owner, "name": name, "cursor": cursor,
        })
        connection = graphql_connection(payload)
        total = connection.get("totalCount")
        if type(total) is not int or total < 0:
            raise AuditError("Немає загальної кількості відкритих PR у GraphQL")
        total_open = total
        for pr in connection["nodes"]:
            if not isinstance(pr, dict):
                raise AuditError("Некоректний PR у GraphQL")
            number = pr.get("number")
            if type(number) is not int or number <= 0 or number in seen:
                raise AuditError("Некоректний або повторений номер PR у GraphQL")
            seen.add(number)
            if number > pr_number:
                continue
            records.append({"number": number, "files": graphql_files(repo, pr, rest_fetch)})
        page = connection.get("pageInfo")
        if (not isinstance(page, dict)
                or type(page.get("hasNextPage")) is not bool):
            raise AuditError("Немає ознаки завершення пагінації GraphQL")
        if not page["hasNextPage"]:
            if pr_number not in seen:
                raise AuditError(f"PR #{pr_number} відсутній серед відкритих")
            # Курсорна пагінація може тихо перескочити PR, якщо набір
            # змінився між сторінками. Зібраних номерів не може бути менше
            # за оголошену кількість: менше — це втрачений PR, тобто
            # потенційно втрачений перетин.
            if len(seen) < total_open:
                raise AuditError(
                    f"Перелік відкритих PR у GraphQL неповний: "
                    f"зібрано {len(seen)} з {total_open}"
                )
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


def emit_skip(pr_number: int, reason: str) -> int:
    """Позначити пропуск і зупинити обов'язковий гейт кодом 2.

    Пропуск — окремий стан, не «перетинів немає»: у JSON видно
    ``"status": "skipped"`` і причину.
    """
    print(json.dumps(
        {"pr": pr_number, "status": "skipped", "reason": reason},
        ensure_ascii=False, indent=2,
    ))
    print(reason)
    print(f"::warning::{reason}")
    return 2


def main(argv=None, *, opener=request.urlopen, sleep=time.sleep) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--pr", type=int, required=True, help="Номер відкритого PR")
    parser.add_argument("--strict", action="store_true", help="Завершити з кодом 1 за перетину")
    parser.add_argument("--snapshot", type=Path, help="Офлайновий JSON: {'pulls': [{'number': N, 'files': [...]}]}")
    parser.add_argument("--max-wait", type=float, default=DEFAULT_MAX_WAIT,
                        help="Скільки секунд сумарно чекати на скидання ліміту запитів")
    args = parser.parse_args(argv)
    token = ""
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
            calls = [0]

            def graphql_fetch(query, variables):
                calls[0] += 1
                return get_graphql(
                    query, variables, token,
                    opener=opener, sleep=sleep, max_wait=args.max_wait,
                )

            def rest_fetch(path):
                calls[0] += 1
                return get_json(
                    path, token, opener=opener, sleep=sleep, max_wait=args.max_wait,
                )

            records = read_live_graphql(args.repo, args.pr, graphql_fetch, rest_fetch)
            print(f"Запитів до GitHub API: {calls[0]}", file=sys.stderr)
        return run(args.pr, records, args.strict)
    except AuditSkipped as exc:
        return emit_skip(args.pr, redact(str(exc), token))
    except (AuditError, OSError, ValueError) as exc:
        # Остання лінія оборони: жодне повідомлення не друкується без редагування.
        print(f"КООРД-ПОМИЛКА: {redact(str(exc), token)}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
