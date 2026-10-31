#!/usr/bin/env python3
"""Виявити змінені шляхи, спільні з ранішими відкритими GitHub PR.

Читання API — тільки через GET. Це перевірка перетину шляхів, а не CLAIM,
академічна рецензія чи автоматична підстава для злиття.

Діагностика помилок API свідомо інформативна: друкуємо HTTP-статус, заголовки
лімітів (X-RateLimit-Remaining, X-RateLimit-Reset, Retry-After), URL запиту і
перші 200 символів тіла відповіді. Токен не друкується ні повністю, ні
частково: у діагностику потрапляють лише відповідь сервера і адреса, а
заголовки запиту не виводяться ніколи.

Три стани розрізняються навмисно:

* 429 або 403 із ознаками ліміту — стан інфраструктури GitHub, не дефект PR.
  Перевірка спершу чекає (з повагою до Retry-After і X-RateLimit-Reset), а
  якщо ліміт не минув — голосно позначає «ПРОПУЩЕНО» і не валить збірку.
* 401 або 403 без ознак ліміту — дефект конфігурації: токен недійсний або
  без прав. Це червоний результат із названою причиною.
* мережа, таймаут, 5xx — теж не провина PR: позначаємо як пропущене.

Невалідний JSON, обрізаний перелік, відсутній PR і перетин шляхів лишаються
червоними: послаблено лише реакцію на інфраструктуру, не на сам гейт.
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

BODY_LIMIT = 200
RATE_HEADERS = ("X-RateLimit-Remaining", "X-RateLimit-Reset", "Retry-After")
MAX_SINGLE_WAIT = 60.0  # секунд на одну паузу
DEFAULT_MAX_WAIT = 45.0  # секунд на всі паузи одного запуску
MAX_ATTEMPTS = 3  # спроб на один запит: нульовий Retry-After не має зациклити


class AuditError(Exception):
    """Стан не можна надійно перевірити; зелений результат заборонений."""


class TokenError(AuditError):
    """Токен недійсний або без прав: це дефект конфігурації, а не PR."""


class AuditSkipped(Exception):
    """Інфраструктурна умова (ліміт, мережа, 5xx): не дефект PR.

    Збірку не валить, але й не оголошує перетин відсутнім: результат
    позначається як ПРОПУЩЕНО з названою причиною.
    """


class Failure:
    """Результат класифікації збою: вид причини і готова діагностика."""

    __slots__ = ("url", "kind", "diagnostic")

    def __init__(self, url: str, kind: str, diagnostic: str) -> None:
        self.url = url
        self.kind = kind  # "limit" | "token" | "network" | "invalid"
        self.diagnostic = diagnostic


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


def describe(exc: BaseException, url: str) -> Failure:
    """Класифікувати збій і скласти діагностику без токена й без заголовків запиту."""
    status = _status(exc)
    headers = _headers(exc)
    body = _body(exc)
    text = body.strip().replace("\r", " ").replace("\n", " ")[:BODY_LIMIT]

    parts = [f"тип={type(exc).__name__}"]
    parts.append(f"HTTP={status}" if status is not None else "HTTP=(немає відповіді)")
    parts.append(f"URL={url}")
    for name in RATE_HEADERS:
        value = headers.get(name)
        if value not in (None, ""):
            parts.append(f"{name}={value}")
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


def get_json(
    path: str,
    token: str,
    *,
    opener=request.urlopen,
    sleep=time.sleep,
    max_wait: float = DEFAULT_MAX_WAIT,
) -> object:
    url = API + path
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ukrainian-books-pr-overlap-audit",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    waited = 0.0
    for attempt in range(1, MAX_ATTEMPTS + 1):
        req = request.Request(url, headers=headers)
        try:
            with opener(req, timeout=15) as reply:
                return json.load(reply)
        except (error.HTTPError, error.URLError, TimeoutError, ValueError, OSError) as exc:
            failure = describe(exc, url)
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
        if type(n) is not int or n <= 0:
            raise AuditError("Некоректні номери в API")
        # Повтор номера між сторінками — не дефект відповіді: перелік
        # відкритих PR читається сторінками, а між запитами PR відкривають і
        # закривають, тож запис зсувається на попередню сторінку й трапляється
        # двічі. Гейт від цього не слабшає: файли беруться з канонічного
        # /pulls/{number}/files для кожного окремого номера, і кожен PR
        # перевіряється рівно один раз.
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


def emit_skip(pr_number: int, reason: str) -> int:
    """Голосно позначити пропуск і не валити збірку."""
    print(json.dumps(
        {"pr": pr_number, "status": "skipped", "reason": reason},
        ensure_ascii=False, indent=2,
    ))
    print(reason)
    print(f"::warning::{reason}")
    return 0


def main(argv=None, *, opener=request.urlopen, sleep=time.sleep) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--pr", type=int, required=True, help="Номер відкритого PR")
    parser.add_argument("--strict", action="store_true", help="Завершити з кодом 1 за перетину")
    parser.add_argument("--snapshot", type=Path, help="Офлайновий JSON: {'pulls': [{'number': N, 'files': [...]}]}")
    parser.add_argument("--max-wait", type=float, default=DEFAULT_MAX_WAIT,
                        help="Скільки секунд сумарно чекати на скидання ліміту запитів")
    args = parser.parse_args(argv)
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
            records = read_live(
                args.repo, args.pr,
                lambda path: get_json(
                    path, token, opener=opener, sleep=sleep, max_wait=args.max_wait
                ),
            )
        return run(args.pr, records, args.strict)
    except AuditSkipped as exc:
        return emit_skip(args.pr, str(exc))
    except (AuditError, OSError, ValueError) as exc:
        print(f"КООРД-ПОМИЛКА: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
