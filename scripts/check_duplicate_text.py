#!/usr/bin/env python3
"""Пошук карток із однаковим санскритським читанням.

Дві картки для різних віршів із тим самим текстом — майже завжди копіпаста:
шаблон скопійовано, а санскрит забули замінити. Схема цього не ловить, бо
кожна картка окремо цілком валідна.

Порівняння йде за полем ``sanskrit`` без пробілів і без маркера вірша:
розмітка й переноси не повинні давати хибних збігів.

За замовчуванням — звіт (rc=0), з ``--strict`` — провал.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

try:  # імпорт як модуля (тести)
    from scripts.check_editorial_cards import CARDS
except ImportError:  # запуск як python3 scripts/check_duplicate_text.py
    from check_editorial_cards import CARDS

MARKER = re.compile(r"\|\|[^|]*\|[^|]*\|\|")
NOISE = re.compile(r"[\s|।]+")


def normalize(text: str) -> str:
    """Згорнути текст до порівнюваної форми."""
    return NOISE.sub("", MARKER.sub("", text)).casefold()


def find_duplicates(cards: list[tuple[str, str]]) -> dict[str, list[str]]:
    """Згрупувати id карток за однаковим нормалізованим текстом."""
    groups: dict[str, list[str]] = defaultdict(list)
    for verse, text in cards:
        key = normalize(text)
        if key:
            groups[key].append(verse)
    return {key: sorted(ids) for key, ids in groups.items() if len(ids) > 1}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cards", type=Path, default=CARDS)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    # Відсутній або підмінений каталог не є доказом відсутності повторів.
    if args.cards.is_symlink() or not args.cards.is_dir():
        print(f"ПОМИЛКА: каталог карток недоступний або непридатний: {args.cards}",
              file=sys.stderr)
        return 2

    cards: list[tuple[str, str]] = []
    count = 0
    if args.cards.exists():
        for file in sorted(args.cards.rglob("*.json")):
            count += 1
            try:
                card = json.loads(file.read_text(encoding="utf-8"))
            except (UnicodeError, OSError, json.JSONDecodeError):
                continue  # пошкоджений JSON ловить схема
            if not isinstance(card, dict):
                continue
            verse, sanskrit = card.get("id"), card.get("sanskrit")
            if isinstance(verse, str) and isinstance(sanskrit, str):
                cards.append((verse, sanskrit))
    if count == 0:
        print(f"ПОМИЛКА: у каталозі карток немає JSON для перевірки: {args.cards}",
              file=sys.stderr)
        return 2
    duplicates = find_duplicates(cards)
    if not duplicates:
        print(f"ОДНАКОВИЙ ТЕКСТ: {count} карток, повторів немає")
        return 0
    print(f"ОДНАКОВИЙ ТЕКСТ: {len(duplicates)} груп у {count} картках")
    for ids in duplicates.values():
        print("  однакове читання: " + ", ".join(ids))
    if args.strict:
        print("ПОМИЛКА: --strict забороняє однаковий текст у різних картках",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
