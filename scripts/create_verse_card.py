#!/usr/bin/env python3
"""Створити незаповнену картку вірша з канонічного локального шаблону."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSE_ID = re.compile(r"([1-9]|1[0-9]|20)\.([1-9][0-9]*)\Z")
EMPTY_FIELDS = (
    "author", "sanskrit", "iast", "grammar", "literal_meaning",
    "ukrainian_translation", "commentary",
)


def verse_limit(root: Path, chapter: int) -> int:
    """Отримати межу глави з реєстру, не з кількості XML-ID у SARIT."""
    path = root / "research" / "ashtavakra" / "registry-20-chapters.csv"
    with path.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            if row["глава"] == str(chapter):
                return int(row["GRETIL_віршів"])
    raise ValueError(f"Глави {chapter} немає у локальному реєстрі")


def build_card(root: Path, verse_id: str) -> dict:
    """Завантажити лише порожній шаблон; не створювати наукових тверджень."""
    match = VERSE_ID.fullmatch(verse_id)
    if not match:
        raise ValueError("Номер має вигляд N.M (1–20; без нулів на початку)")
    chapter, verse = map(int, match.groups())
    limit = verse_limit(root, chapter)
    if verse > limit:
        raise ValueError(f"Вірш {verse_id} виходить за межі глави {chapter} (1–{limit})")

    template_path = root / "docs" / "VERSE_CARD_TEMPLATE.json"
    with template_path.open(encoding="utf-8") as file:
        card = json.load(file)

    if card.get("schema_version") != 1 or card.get("status") != "чернетка":
        raise ValueError("Шаблон має невідому версію схеми або недозволений статус")
    if any(card.get(field, "ВІДСУТНЄ ПОЛЕ") is not None for field in EMPTY_FIELDS):
        raise ValueError("Шаблон містить заповнені дослідницькі поля")
    if card.get("variants") != [] or card.get("variants_checked") is not False:
        raise ValueError("Шаблон неправомірно заявляє перевірку різночитань")
    rights = card.get("rights", {})
    review = card.get("review", {})
    if (rights.get("basis") is not None or rights.get("evidence_url") is not None
            or rights.get("verified") is not False or rights.get("own_ukrainian_text") is not False
            or any(review.get(k, "ВІДСУТНЄ ПОЛЕ") is not None
                   for k in ("reviewer", "reviewed_on", "review_url"))):
        raise ValueError("Шаблон не є незаповненою чернеткою прав і рецензії")
    sources = card.get("sources", {})
    for name in ("gretil", "sarit"):
        source = sources.get(name, {})
        if not isinstance(source.get("url"), str) or not source["url"].startswith("https://"):
            raise ValueError(f"У шаблоні відсутня HTTPS-адреса джерела {name}")
        if source.get("checked_on") is not None:
            raise ValueError("Шаблон помилково містить дату перевірки джерела")

    card["id"] = verse_id
    sources["gretil"]["locator"] = f"Avg_{verse_id}"
    # У SARIT 18.95 не має власного XML-ID: позиція міститься у verse_18.96.
    sources["sarit"]["locator"] = (
        "verse_18.96#18.95" if verse_id == "18.95" else f"verse_{verse_id}"
    )
    return card


def create_card(root: Path, verse_id: str, *, preview: bool = False) -> str:
    """Повернути JSON для перегляду або створити файл виключним записом."""
    card = build_card(root, verse_id)
    payload = json.dumps(card, ensure_ascii=False, indent=2) + "\n"
    if preview:
        return payload

    directory = root / "editorial" / "cards"
    if directory.is_symlink():
        raise ValueError("Каталог карток не може бути символьним посиланням")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{verse_id}.json"
    # 'x' не перезаписує наявний файл навіть за одночасної роботи агентів.
    with path.open("x", encoding="utf-8") as file:
        file.write(payload)
    return str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("verse_id", help="номер вірша N.M, наприклад 18.95")
    parser.add_argument("--preview", action="store_true", help="вивести JSON без запису")
    args = parser.parse_args(argv)
    try:
        result = create_card(ROOT, args.verse_id, preview=args.preview)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"Не створено картку: {exc}", file=sys.stderr)
        return 1
    if args.preview:
        print(result, end="")
    else:
        print(f"Створено чернетку: {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
