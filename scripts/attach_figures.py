#!/usr/bin/env python3
"""Додає до зверстаних віршів власні ілюстрації, якщо вони існують.

Два каталоги, два різні види матеріалу:

* `ilustratsii-naratyvni/` — сюжетні малюнки: показують ситуацію вірша
  (людина з торбиною на стежці, змія замість мотузки тощо);
* `ilustratsii/` — машинні схеми, які генерує `build_verse_schemas.py`.

Скрипт віддає перевагу сюжетній ілюстрації: вона розказує, а не позначає.
Якщо сюжетної немає — бере схему. Якщо немає нічого — вірш лишається без
рисунка.

Посилання додається лише тоді, коли PDF ілюстрації вже існує: конвертація
SVG → PDF виконується кроком збірки ДО цього скрипта.

Скрипт ідемпотентний: якщо рисунок до вірша вже вставлено, він нічого не робить.

Запуск (після конвертації SVG → PDF):
    python3 scripts/attach_figures.py            # вставити
    python3 scripts/attach_figures.py --check    # лише порахувати
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOK_DIR = ROOT / "books" / "ashtavakra-gita"
VERSES = ROOT / "books" / "ashtavakra-hita-pilot" / "generated" / "verses.tex"

# Порядок важливий: сюжетна ілюстрація розказує ситуацію, схема лише позначає.
SOURCES = ("ilustratsii-naratyvni", "ilustratsii")

VERSE = re.compile(r"^\\virs\{([0-9]+\.[0-9]+)\}")
SOURCES_LINE = "\\virsources{"
FIGURE = "\\virfig{"


def figure_for(ident: str) -> str | None:
    prefix = ident.replace(".", "-")
    for folder in SOURCES:
        directory = BOOK_DIR / folder
        if not directory.is_dir():
            continue
        for svg in sorted(directory.glob(f"{prefix}-*.svg")):
            if (directory / (svg.stem + ".pdf")).is_file():
                return f"../ashtavakra-gita/{folder}/{svg.stem}.pdf"
    return None


def attach(text: str) -> tuple[str, int, int]:
    lines = text.split("\n")
    out: list[str] = []
    current: str | None = None
    done: set[str] = set()
    inserted = 0
    for line in lines:
        match = VERSE.match(line)
        if match:
            current = match.group(1)
        if line.startswith(FIGURE) and current:
            done.add(current)
        if line.startswith(SOURCES_LINE) and current and current not in done:
            figure = figure_for(current)
            if figure:
                out.append("\\virfig{%s}" % figure)
                done.add(current)
                inserted += 1
        out.append(line)
    return "\n".join(out), inserted, len(done)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if not VERSES.is_file():
        print(f"Немає верстки: {VERSES}", file=sys.stderr)
        return 1
    text = VERSES.read_text(encoding="utf-8")
    updated, inserted, with_figure = attach(text)
    if not args.check and inserted:
        VERSES.write_text(updated, encoding="utf-8")
    print(json.dumps({
        "verses_with_figure": with_figure,
        "inserted_now": inserted,
        "written": (not args.check and bool(inserted)),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
