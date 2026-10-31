#!/usr/bin/env python3
"""Звітувати про формальне охоплення редакторських карток без зміни файлів."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from check_editorial_cards import validate_card, valid_verse_ids

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CARDS = ROOT / "editorial" / "cards"
STATES = ("чернетка", "перевірено", "рецензовано")
DISCLAIMER = (
    "Це підрахунок формально валідних карток і заявлених у JSON статусів. "
    "Валідатор не встановлює незалежності рецензій, точності санскриту "
    "чи прав на публікацію."
)


def count_coverage(expected: set[str], folder: Path) -> dict:
    """Детермінований підрахунок; зіпсовані картки не стають «готовими»."""
    chapters = []
    for n in range(1, 21):
        maximum = sum(x.startswith(f"{n}.") for x in expected)
        chapters.append({
            "глава": n, "очікувано": maximum, "карток": 0,
            "відсутні": maximum, "статуси": {state: 0 for state in STATES}
        })
    errors: list[str] = []
    found: dict[str, str] = {}

    # Заборонити symlink у будь-якій частині шляху, включно з батьками.
    # Інакше editorial/ (symlink) / cards/ (звичайна тека) обходить перевірку.
    link_component = next((part for part in (folder, *folder.parents) if part.is_symlink()), None)
    if link_component is not None:
        errors.append(f"Компонент шляху карток є символьним посиланням: {link_component}")
    elif folder.exists() and not folder.is_dir():
        errors.append(f"Шлях карток не є каталогом: {folder}")
    elif folder.is_dir():
        for path in sorted(folder.rglob("*")):
            relative = path.relative_to(folder)
            if path.is_symlink():
                errors.append(f"Символьне посилання у картках: {relative}")
                continue
            if not path.is_file() or path.suffix != ".json":
                continue
            try:
                card = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                errors.append(f"{relative}: недійсний JSON: {exc}")
                continue
            problems = validate_card(card, expected, filename=path.name)
            if path.parent != folder:
                problems.append("Картка повинна лежати безпосередньо в editorial/cards")
            verse = card.get("id") if isinstance(card, dict) else None
            if isinstance(verse, str) and verse in found:
                problems.append(f"Повторний ID {verse} (перша картка: {found[verse]})")
            if problems:
                errors.extend(f"{relative}: {message}" for message in problems)
                continue
            found[verse] = str(relative)
            row = chapters[int(verse.split(".")[0]) - 1]
            row["карток"] += 1
            row["відсутні"] -= 1
            row["статуси"][card["status"]] += 1

    summary = {
        "очікувано": len(expected),
        "карток": sum(row["карток"] for row in chapters),
        "відсутні": sum(row["відсутні"] for row in chapters),
        "статуси": {
            state: sum(row["статуси"][state] for row in chapters)
            for state in STATES
        }
    }
    if sum(row["очікувано"] for row in chapters) != len(expected):
        errors.append("Реєстр містить ID поза главами 1–20")
    return {
        "стан": "помилка" if errors else "гаразд",
        "застереження": DISCLAIMER,
        "підсумок": summary,
        "глави": chapters,
        "помилки": sorted(errors),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cards", type=Path, default=DEFAULT_CARDS,
                        help="каталог JSON-карток (типово editorial/cards)")
    parser.add_argument("--registry", type=Path,
                        default=ROOT / "research/ashtavakra/registry-20-chapters.csv",
                        help="канонічний порозділовий CSV-реєстр")
    args = parser.parse_args(argv)
    try:
        result = count_coverage(valid_verse_ids(args.registry), args.cards)
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        result = {"стан": "помилка", "помилки": [f"Неможливо прочитати реєстр: {exc}"]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["стан"] == "гаразд" else 1


if __name__ == "__main__":
    sys.exit(main())
