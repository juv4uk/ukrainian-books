#!/usr/bin/env python3
"""Офлайновий контроль хронології дат свідків і рецензій у редакторських картках.

Машина перевіряє тільки правдоподібність дати; не засвідчує реального
відвідування джерела, незалежності рецензента або юридичної чинності прав.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "editorial" / "cards"
DATE_FIELDS = (
    ("sources", "gretil", "checked_on"),
    ("sources", "sarit", "checked_on"),
    ("review", "reviewed_on"),
)


def inspect_date(card: dict, field: tuple[str, ...], today: date) -> list[str]:
    current: object = card
    for key in field:
        if not isinstance(current, dict):
            return []  # Структуру перевіряє check_editorial_cards.py
        current = current.get(key)
    if current is None:
        return []
    name = ".".join(field)
    if not isinstance(current, str):
        return [f"{name}: дата має бути рядком YYYY-MM-DD або null"]
    try:
        parsed = date.fromisoformat(current)
    except ValueError:
        return [f"{name}: недійсна дата {current!r}"]
    if parsed.isoformat() != current:
        return [f"{name}: неканонічна дата {current!r}, потрібна YYYY-MM-DD"]
    if parsed > today:
        return [f"{name}: майбутня дата {current} після {today.isoformat()} (UTC)"]
    return []


def check_directory(folder: Path, today: date) -> tuple[int, list[str]]:
    """Повертає кількість карток і помилки, з контрольованим часом для тестів."""
    if folder.is_symlink():
        return 0, [f"{folder}: каталог карток не може бути символічним посиланням"]
    if not folder.exists():
        return 0, []
    if not folder.is_dir():
        return 0, [f"{folder}: очікується каталог карток"]
    checked = 0
    errors: list[str] = []
    for file in sorted(folder.rglob("*.json")):
        checked += 1
        if file.is_symlink():
            errors.append(f"{file}: символьне посилання замість картки")
            continue
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"{file}: не вдалося прочитати JSON: {exc}")
            continue
        if not isinstance(data, dict):
            errors.append(f"{file}: очікується JSON-об'єкт")
            continue
        for field in DATE_FIELDS:
            errors.extend(f"{file}: {err}" for err in inspect_date(data, field, today))
    return checked, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cards", type=Path, default=CARDS,
                        help="Шлях до каталогу редакторських JSON-карток")
    args = parser.parse_args()
    today = datetime.now(timezone.utc).date()
    count, errors = check_directory(args.cards, today)
    print(json.dumps({
        "status": "ok" if not errors else "failed",
        "checked_cards": count,
        "as_of_utc": today.isoformat(),
        "errors": errors,
    }, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
