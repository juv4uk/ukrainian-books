#!/usr/bin/env python3
"""Перевірка, чи текстові поля картки не обірвані.

Схема перевіряє, що поле заповнене. Вона не бачить, що поле **обірване**:
обрізаний посеред слова текст лишається валідним JSON, і саме так двічі
за одну сесію до репозиторію доходили зіпсовані картки.

Правила свідомо мінімальні — тільки те, що можна перевірити без
тлумачення:

* ``sanskrit`` і ``iast`` закінчуються дандою (``|`` або ``।``);
* ``literal_meaning``, ``ukrainian_translation``, ``commentary``
  закінчуються знаком кінця речення;
* ``iast`` не містить кирилиці або деванаґарі;
* ``ukrainian_translation`` містить кирилицю.

За замовчуванням — звіт (rc=0), з ``--strict`` — провал.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:  # імпорт як модуля (тести)
    from scripts.check_editorial_cards import CARDS
except ImportError:  # запуск як python3 scripts/check_card_text.py
    from check_editorial_cards import CARDS

SENTENCE_END = (".", "!", "?", "…", "»", ")", "”")
CYRILLIC = ("\u0400", "\u04FF")
DEVANAGARI = ("\u0900", "\u097F")


def _has_char(text: str, span: tuple[str, str]) -> bool:
    return any(span[0] <= char <= span[1] for char in text)


def check_card(card: object, name: str) -> list[str]:
    problems: list[str] = []
    if not isinstance(card, dict):
        return [f"{name}: не об'єкт"]
    for field in ("sanskrit", "iast"):
        value = card.get(field)
        if isinstance(value, str) and value.strip() and not value.rstrip().endswith(("|", "।")):
            problems.append(f"{name}: {field} не закінчується дандою — можливо, обірвано")
    for field in ("literal_meaning", "ukrainian_translation", "commentary"):
        value = card.get(field)
        if isinstance(value, str) and value.strip() and not value.rstrip().endswith(SENTENCE_END):
            problems.append(f"{name}: {field} не закінчується кінцем речення")
    iast = card.get("iast")
    if isinstance(iast, str) and (_has_char(iast, CYRILLIC) or _has_char(iast, DEVANAGARI)):
        problems.append(f"{name}: в iast є кирилиця або деванаґарі")
    ukrainian = card.get("ukrainian_translation")
    if isinstance(ukrainian, str) and ukrainian.strip() and not _has_char(ukrainian, CYRILLIC):
        problems.append(f"{name}: український переклад без кирилиці")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cards", type=Path, default=CARDS)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    problems: list[str] = []
    count = 0
    if args.cards.exists():
        for file in sorted(args.cards.rglob("*.json")):
            count += 1
            try:
                card = json.loads(file.read_text(encoding="utf-8"))
            except (UnicodeError, OSError, json.JSONDecodeError):
                continue  # пошкоджений JSON ловить схема
            problems.extend(check_card(card, file.name))
    if not problems:
        print(f"ТЕКСТ КАРТОК: {count} перевірено, обірваних полів немає")
        return 0
    print(f"ТЕКСТ КАРТОК: {len(problems)} зауважень у {count} картках")
    for problem in problems:
        print("  " + problem)
    if args.strict:
        print("ПОМИЛКА: --strict вимагає цілісних текстових полів", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
