#!/usr/bin/env python3
"""РЕД-06: заборонити повторені ключі редакторських JSON-карток."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARDS = Path("editorial/cards")
TEMPLATE = Path("docs/VERSE_CARD_TEMPLATE.json")


class DuplicateKeyError(ValueError):
    """Два однакові ключі одного об'єкта в JSON не допускаються."""


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """object_pairs_hook працює навіть у вкладених об'єктах та масивах."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"повторений JSON-ключ {key!r}")
        result[key] = value
    return result


def load_unique(path: Path) -> object:
    """Суворе UTF-8, JSON та відсутність прихованого перевизначення ключів."""
    return json.loads(path.read_text(encoding="utf-8", errors="strict"),
                      object_pairs_hook=unique_object)


def audit(root: Path) -> dict:
    errors: list[str] = []
    checked_cards = 0
    checked_template = False
    template = root / TEMPLATE
    if template.is_symlink():
        errors.append(f"{TEMPLATE.as_posix()}: символічне посилання не дозволено")
    elif not template.is_file():
        errors.append(f"{TEMPLATE.as_posix()}: відсутній шаблон")
    else:
        checked_template = True
        try:
            load_unique(template)
        except (ValueError, UnicodeError, OSError) as exc:
            errors.append(f"{TEMPLATE.as_posix()}: {exc}")

    cards = root / CARDS
    if cards.is_symlink():
        errors.append(f"{CARDS.as_posix()}: символічне посилання не дозволено")
    elif cards.exists() and not cards.is_dir():
        errors.append(f"{CARDS.as_posix()}: очікується каталог")
    elif cards.is_dir():
        for path in sorted(cards.rglob("*")):
            rel = path.relative_to(root).as_posix()
            if path.is_symlink():
                errors.append(f"{rel}: символічне посилання не дозволено")
                continue
            if not path.is_file() or path.suffix.lower() != ".json":
                continue
            checked_cards += 1
            try:
                load_unique(path)
            except (ValueError, UnicodeError, OSError) as exc:
                errors.append(f"{rel}: {exc}")

    return {
        "status": "failed" if errors else "ok",
        "checked_cards": checked_cards,
        "checked_template": checked_template,
        "errors": errors,
        "notice": "Це контроль JSON-структури, не наукова чи правова рецензія",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    result = audit(args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
