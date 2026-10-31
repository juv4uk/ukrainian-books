#!/usr/bin/env python3
"""Незмінність канонічного тексту «ВОЛЬНІСТЬ» (офлайн, без залежностей)."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

# SHA-256 точних UTF-8 байтів juv4uk/sens/LICENSE.
# Git blob SHA: a49660652423dcc5352c11456f31bca8806c0d25.
# Зміни цього значення не допускаються без окремого рішення власника
# щодо канону; зміна обох копій ліцензії не повинна проходити перевірку.
CANONICAL_SHA256 = "395fc9e43412edde4884568d5b0949f1d7c992f6503946746556eb1bb52b9bb0"
CANONICAL_BYTES = 649
LICENSE_FILES = ("LICENSE", "VOLNOST.md")


def check_volnost(root: Path) -> list[str]:
    """Повертає помилки, не змінюючи вміст файлів і не використовуючи мережу."""
    errors: list[str] = []
    contents: dict[str, bytes] = {}

    for name in LICENSE_FILES:
        path = root / name
        try:
            data = path.read_bytes()
        except OSError as exc:
            errors.append(f"Неможливо прочитати {name}: {exc}")
            continue

        contents[name] = data
        if len(data) != CANONICAL_BYTES:
            errors.append(
                f"{name}: довжина {len(data)} байтів, очікується {CANONICAL_BYTES}"
            )
        actual = hashlib.sha256(data).hexdigest()
        if actual != CANONICAL_SHA256:
            errors.append(
                f"{name}: контрольна сума SHA-256 {actual} "
                f"не збігається з каноном {CANONICAL_SHA256}"
            )

    if all(name in contents for name in LICENSE_FILES):
        if contents["LICENSE"] != contents["VOLNOST.md"]:
            errors.append("LICENSE і VOLNOST.md не збігаються побайтово")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Незмінність канонічної ліцензії «ВОЛЬНІСТЬ»"
    )
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1],
        help="Корінь репозиторію (типово визначається за шляхом скрипту)",
    )
    args = parser.parse_args()
    errors = check_volnost(args.root)
    print(json.dumps({
        "статус": "успіх" if not errors else "помилка",
        "канон": "juv4uk/sens/LICENSE",
        "sha256": CANONICAL_SHA256,
        "помилки": errors,
    }, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
