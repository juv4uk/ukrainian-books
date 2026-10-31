#!/usr/bin/env python3
"""Прогалини в нумерації редакторських карток.

Перевірка схеми бачить лише подані картки: 30 карток можуть виглядати
цілком здорово, навіть якщо в главі бракує середини. Цей скрипт шукає саме
такі дірки й нічого не змінює.

Прогалиною вважається відсутній вірш у главі, де вже є хоч одна картка.
Глава без жодної картки прогалиною не вважається — інакше звіт завжди
складався б із 298 рядків і його ніхто не читав би.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:  # імпорт як модуля (тести)
    from scripts.check_editorial_cards import CARDS, ID, valid_verse_ids
except ImportError:  # запуск як python3 scripts/check_verse_gaps.py
    from check_editorial_cards import CARDS, ID, valid_verse_ids

ROOT = Path(__file__).resolve().parents[1]


def present_ids(folder: Path) -> set[str]:
    """ID наявних карток; пошкоджені файли пропускаються — їх ловить схема."""
    found: set[str] = set()
    if not folder.exists():
        return found
    for file in sorted(folder.rglob("*.json")):
        try:
            card = json.loads(file.read_text(encoding="utf-8"))
        except (UnicodeError, OSError, json.JSONDecodeError):
            continue
        verse = card.get("id") if isinstance(card, dict) else None
        if isinstance(verse, str) and ID.fullmatch(verse):
            found.add(verse)
    return found


def find_gaps(present: set[str], expected: set[str]) -> dict[int, list[str]]:
    """Відсутні номери в початих главах, у порядку номерів, а не рядків."""
    started = {int(item.split(".")[0]) for item in present}
    gaps: dict[int, list[str]] = {}
    for verse in expected - present:
        chapter = int(verse.split(".")[0])
        if chapter in started:
            gaps.setdefault(chapter, []).append(verse)
    return {
        chapter: sorted(items, key=lambda item: int(item.split(".")[1]))
        for chapter, items in sorted(gaps.items())
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cards", type=Path, default=CARDS,
                        help="Тека реальних JSON-карток")
    parser.add_argument("--strict", action="store_true",
                        help="Провалити перевірку, якщо прогалини є")
    args = parser.parse_args()
    # Не ототожнюємо відсутнє джерело даних із відсутністю прогалин.
    # Символьні посилання можуть вивести перевірку за межі заданої теки.
    if args.cards.is_symlink():
        print(f"ПОМИЛКА: каталог карток є символічним посиланням: {args.cards}",
              file=sys.stderr)
        return 2
    if not args.cards.is_dir():
        print(f"ПОМИЛКА: каталог карток не існує або не є каталогом: {args.cards}",
              file=sys.stderr)
        return 2
    try:
        expected = valid_verse_ids()
    except (OSError, ValueError) as exc:
        print(f"ПОМИЛКА: {exc}", file=sys.stderr)
        return 1
    present = present_ids(args.cards)
    gaps = find_gaps(present, expected)
    if not gaps:
        print(f"ПРОГАЛИНИ: немає — {len(present)} карток, нумерація початих глав суцільна")
        return 0
    missing = sum(len(items) for items in gaps.values())
    print(f"ПРОГАЛИНИ: бракує {missing} віршів у {len(gaps)} главах")
    for chapter, items in gaps.items():
        print(f"  глава {chapter}: " + ", ".join(items))
    if args.strict:
        print("ПОМИЛКА: --strict вимагає суцільної нумерації", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
