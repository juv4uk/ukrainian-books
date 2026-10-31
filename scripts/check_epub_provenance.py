#!/usr/bin/env python3
"""Офлайновий запобіжник EPUB поза виданнями з паспортом походження.

Не підтверджує авторських прав, достовірності паспорта або дозволу на
розповсюдження. Ці питання окремо перевіряє check_provenance.py і редактор.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def audit(root: Path) -> dict[str, object]:
    """Шукати EPUB незалежно від регістру розширення, не читаючи їхній вміст."""
    errors: list[str] = []
    checked = 0
    if not root.is_dir():
        return {"status": "failed", "checked_epub": 0,
                "errors": [f"{root}: корінь сховища не є каталогом"]}
    books = root / "books"
    if books.is_symlink():
        errors.append("books/: символічне посилання замість каталогу")
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if ".git" in relative.parts or path.suffix.casefold() != ".epub":
            continue
        checked += 1
        name = relative.as_posix()
        if path.is_symlink():
            errors.append(f"{name}: EPUB не може бути символічним посиланням")
            continue
        if not path.is_file():
            errors.append(f"{name}: EPUB має бути звичайним файлом")
            continue
        parts = relative.parts
        if len(parts) < 3 or parts[0] != "books":
            errors.append(f"{name}: EPUB дозволений лише у books/<видання>/")
            continue
        edition = books / parts[1]
        passport = edition / "PROVENANCE.md"
        if edition.is_symlink() or passport.is_symlink():
            errors.append(f"{name}: символічне посилання у шляху до паспорта")
        elif not passport.is_file():
            errors.append(f"{name}: немає books/{parts[1]}/PROVENANCE.md")
    return {
        "status": "failed" if errors else "ok",
        "checked_epub": checked,
        "errors": errors,
        "notice": "Структурний контроль: успіх не є підтвердженням прав чи дозволом на публікацію",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT,
                        help="Корінь сховища (типово — батько scripts/)")
    args = parser.parse_args()
    result = audit(args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
