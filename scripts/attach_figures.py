#!/usr/bin/env python3
"""Додає до зверстаних віршів власні схеми, якщо вони існують.

Схеми лежать у `books/ashtavakra-gita/ilustratsii/N-M-назва.svg` і крок збірки
конвертує їх у PDF. Цей скрипт вставляє `\\virfig{...}` у згенеровану верстку
`books/ashtavakra-hita-pilot/generated/verses.tex` — безпосередньо перед рядком
`\\virsources`, яким завершується кожен блок вірша.

Скрипт ідемпотентний: якщо рисунок до вірша вже вставлено, він нічого не робить.
Посилання додається лише тоді, коли PDF схеми вже існує: частина SVG у каталозі —
ручні ілюстрації, яких конвертер не торкається, і посилання на них зламало б збірку.

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
FIGURES = ROOT / "books" / "ashtavakra-gita" / "ilustratsii"
VERSES = ROOT / "books" / "ashtavakra-hita-pilot" / "generated" / "verses.tex"
PREFIX = "../ashtavakra-gita/ilustratsii/"

VERSE = re.compile(r"^\\virs\{([0-9]+\.[0-9]+)\}")
SOURCES = "\\virsources{"
FIGURE = "\\virfig{"


def figure_for(ident: str) -> str | None:
    if not FIGURES.is_dir():
        return None
    for svg in sorted(FIGURES.glob(f"{ident.replace('.', '-')}-*.svg")):
        # Беремо лише ту схему, для якої збірка вже зробила PDF: частина SVG
        # у каталозі — ручні ілюстрації, яких конвертер не торкається.
        if (FIGURES / (svg.stem + ".pdf")).is_file():
            return PREFIX + svg.stem + ".pdf"
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
        if line.startswith(SOURCES) and current and current not in done:
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
