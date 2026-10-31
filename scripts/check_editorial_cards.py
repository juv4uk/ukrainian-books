#!/usr/bin/env python3
"""Контроль власних редакторських карток без копіювання сторонніх корпусів."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "research/ashtavakra/registry-20-chapters.csv"
TEMPLATE = ROOT / "docs/VERSE_CARD_TEMPLATE.json"
CARDS = ROOT / "editorial/cards"
STATUS = {"чернетка", "перевірено", "рецензовано"}
FIELDS = (
    "schema_version", "id", "work", "status", "author", "sources", "sanskrit",
    "iast", "grammar", "literal_meaning", "ukrainian_translation",
    "commentary", "variants", "variants_checked", "rights", "review",
)
SCHOLARLY = (
    "sanskrit", "iast", "grammar", "literal_meaning",
    "ukrainian_translation", "commentary",
)
ID = re.compile(r"^([1-9]\d*)\.([1-9]\d*)$")


def filled(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def valid_date(value: object) -> bool:
    if not filled(value):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def valid_url(value: object) -> bool:
    if not filled(value):
        return False
    try:
        parsed = urlparse(value)
        return (parsed.scheme == "https" and bool(parsed.hostname)
                and not parsed.username and not parsed.password)
    except ValueError:
        return False


def valid_verse_ids(csv_path: Path = INDEX) -> set[str]:
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    chapters = [row for row in rows if row.get("глава") != "разом"]
    if len(chapters) != 20:
        raise ValueError("Реєстр повинен охоплювати рівно 20 глав")
    ids: set[str] = set()
    for chapter, row in enumerate(chapters, 1):
        if row["глава"] != str(chapter):
            raise ValueError(f"Порушено послідовність глав: {chapter}")
        count = int(row["GRETIL_віршів"])
        if count <= 0:
            raise ValueError(f"Глава {chapter} не містить номерів")
        ids.update(f"{chapter}.{v}" for v in range(1, count + 1))
    if len(ids) != 298:
        raise ValueError(f"Реєстр містить {len(ids)}, очікується 298")
    return ids


def validate_card(card: object, expected: set[str], filename: str | None = None) -> list[str]:
    errors: list[str] = []
    if not isinstance(card, dict):
        return ["Картка має бути JSON-об'єктом"]
    for field in FIELDS:
        if field not in card:
            errors.append(f"Відсутнє поле {field}")
    if type(card.get("schema_version")) is not int or card.get("schema_version") != 1:
        errors.append("Непідтримувана версія схеми")
    verse = card.get("id")
    if not isinstance(verse, str) or not ID.fullmatch(verse) or verse not in expected:
        errors.append(f"Невідомий ідентифікатор вірша: {verse!r}")
    if filename is not None and filename != f"{verse}.json":
        errors.append(f"Назва файлу {filename} не відповідає ID {verse}")
    if card.get("work") != "Аштавакра-ґіта":
        errors.append("Неочікувана назва твору")
    status = card.get("status")
    if not isinstance(status, str) or status not in STATUS:
        errors.append("Невідомий статус")
    author = card.get("author")
    if author is not None and not filled(author):
        errors.append("Ім'я автора має бути непорожнім або null")

    sources = card.get("sources")
    if not isinstance(sources, dict):
        errors.append("sources має бути об'єктом")
        sources = {}
    for witness in ("gretil", "sarit"):
        item = sources.get(witness)
        if not isinstance(item, dict):
            errors.append(f"Відсутній свідок {witness}")
            continue
        url, locator = item.get("url"), item.get("locator")
        if not valid_url(url):
            errors.append(f"{witness}: URL має бути HTTPS")
        if not filled(locator):
            errors.append(f"{witness}: потрібний точний локатор")
        elif isinstance(verse, str):
            special = "verse_18.96#18.95" if verse == "18.95" else f"verse_{verse}"
            required = f"Avg_{verse}" if witness == "gretil" else special
            if locator != required:
                errors.append(f"{witness}: локатор {locator!r} не відповідає {required!r}")
        checked = item.get("checked_on")
        if checked is not None and not valid_date(checked):
            errors.append(f"{witness}: дата перевірки має бути YYYY-MM-DD або null")

    for name in SCHOLARLY:
        value = card.get(name)
        if value is not None and not filled(value):
            errors.append(f"{name}: значення має бути текстом або null")
    variants = card.get("variants")
    if not isinstance(variants, list):
        errors.append("variants має бути списком")
    else:
        for i, value in enumerate(variants):
            if not (isinstance(value, dict) and filled(value.get("witness"))
                    and filled(value.get("note")) and valid_url(value.get("evidence_url"))):
                errors.append(f"variants[{i}]: свідок, власна примітка та HTTPS-доказ обов'язкові")
    if type(card.get("variants_checked")) is not bool:
        errors.append("variants_checked має бути булевим значенням")

    rights = card.get("rights")
    if not isinstance(rights, dict):
        errors.append("rights має бути об'єктом")
        rights = {}
    for name in ("verified", "own_ukrainian_text"):
        if type(rights.get(name)) is not bool:
            errors.append(f"rights.{name} має бути bool")
    for name in ("basis", "evidence_url"):
        value = rights.get(name)
        if value is not None and (not filled(value) if name == "basis" else not valid_url(value)):
            errors.append(f"rights.{name}: неправильне значення")
    review = card.get("review")
    if not isinstance(review, dict):
        errors.append("review має бути об'єктом")
        review = {}
    for name in ("reviewer", "reviewed_on", "review_url"):
        value = review.get(name)
        if value is not None:
            if name == "reviewed_on" and not valid_date(value):
                errors.append("review.reviewed_on має бути YYYY-MM-DD")
            elif name == "review_url" and not valid_url(value):
                errors.append("review.review_url має бути HTTPS")
            elif name == "reviewer" and not filled(value):
                errors.append("review.reviewer має бути непорожнім")

    if status in ("перевірено", "рецензовано"):
        if not filled(author):
            errors.append("Після перевірки має бути відомий автор перекладу")
        for name in SCHOLARLY:
            if not filled(card.get(name)):
                errors.append(f"{name}: не заповнено для статусу {status}")
        for witness in ("gretil", "sarit"):
            if not valid_date(sources.get(witness, {}).get("checked_on")
                              if isinstance(sources.get(witness), dict) else None):
                errors.append(f"{witness}: немає підтвердженої дати звірення")
        if card.get("variants_checked") is not True:
            errors.append("Не перевірено можливі різночитання")
        if rights.get("verified") is not True or rights.get("own_ukrainian_text") is not True:
            errors.append("Не підтверджено права на український текст")
        if not filled(rights.get("basis")) or not valid_url(rights.get("evidence_url")):
            errors.append("Потрібні підстава і HTTPS-доказ прав")
    if status == "рецензовано":
        reviewer = review.get("reviewer")
        if not filled(reviewer) or not valid_date(review.get("reviewed_on")):
            errors.append("Немає імені незалежного рецензента та дати")
        if not valid_url(review.get("review_url")):
            errors.append("Немає HTTPS-посилання на зафіксовану рецензію")
        if filled(reviewer) and filled(author) and reviewer.strip().casefold() == author.strip().casefold():
            errors.append("Автор не може бути власним незалежним рецензентом")
    return errors


def check_directory(folder: Path, expected: set[str]) -> tuple[int, list[str]]:
    errors: list[str] = []
    count = 0
    seen: set[str] = set()
    if not folder.exists():
        return 0, []
    for file in sorted(folder.rglob("*.json")):
        count += 1
        try:
            card = json.loads(file.read_text(encoding="utf-8"))
        except (UnicodeError, OSError, json.JSONDecodeError) as exc:
            errors.append(f"{file}: {exc}")
            continue
        verse = card.get("id") if isinstance(card, dict) else None
        if isinstance(verse, str) and verse in seen:
            errors.append(f"{file}: повторна картка для {verse}")
        if isinstance(verse, str):
            seen.add(verse)
        errors.extend(f"{file}: {msg}" for msg in
                      validate_card(card, expected, filename=file.name))
    return count, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cards", type=Path, default=CARDS,
                        help="Тека реальних JSON-карток (зразок не входить)")
    args = parser.parse_args()
    try:
        expected = valid_verse_ids()
        sample = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        errors = [f"Шаблон: {x}" for x in validate_card(sample, expected)]
        count, card_errors = check_directory(args.cards, expected)
        errors.extend(card_errors)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ПОМИЛКА: {exc}", file=sys.stderr)
        return 1
    print(f"Індекс: {len(expected)} номерів; подано карток: {count}; шаблон: 1")
    if not count:
        print("Карток поки немає. Це перевірка схеми, а не рецензія 298 віршів.")
    for error in errors:
        print("ПОМИЛКА: " + error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
