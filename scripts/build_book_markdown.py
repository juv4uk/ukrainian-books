#!/usr/bin/env python3
"""Складає книжковий текст «Аштавакра-ґіти» з редакторських карток.

Бере **лише наші власні** поля карток — український переклад — і пише
по одному markdown-файлу на главу: `books/ashtavakra-gita/rozdil-N.md`.

Читань цифрових свідків (поля `sanskrit`, `iast`) скрипт не переносить: транскрипції
GRETIL і SARIT мають власні умови, а паспорт дозволяє поширювати лише наш внесок.
Див. `books/ashtavakra-gita/PROVENANCE.md`.

Скрипт використовує тільки стандартну бібліотеку, не робить мережевих запитів
і дає побайтово однаковий результат на однакових вхідних даних.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "editorial" / "cards"
OUT = ROOT / "books" / "ashtavakra-gita"

HEADER = """# Аштавакра-ґіта. Розділ {n}

> Робочий текст українського видання. Переклад власний, узятий з редакторських карток
> `editorial/cards/{n}.*.json`. Санскритське читання тут не відтворюється — воно звірене
> за SARIT і зберігається в картках. Паспорт походження: `PROVENANCE.md`.
"""


def verse_key(path: Path) -> tuple[int, int]:
    chapter, verse = path.stem.split(".")
    return int(chapter), int(verse)


def chapter_cards(chapter: int) -> list[Path]:
    return sorted(
        (p for p in CARDS.glob(f"{chapter}.*.json")),
        key=verse_key,
    )


def render_chapter(chapter: int) -> str:
    lines = [HEADER.format(n=chapter)]
    for path in chapter_cards(chapter):
        card = json.loads(path.read_text(encoding="utf-8"))
        lines.append(f"## {card['id']}")
        lines.append("")
        lines.append(card["ukrainian_translation"].strip())
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str]) -> int:
    chapters = sorted({verse_key(p)[0] for p in CARDS.glob("*.json")})
    if argv:
        chapters = [int(a) for a in argv]
    if not chapters:
        print("немає карток для складання", file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    for chapter in chapters:
        text = render_chapter(chapter)
        target = OUT / f"rozdil-{chapter}.md"
        target.write_text(text, encoding="utf-8")
        print(f"{target.relative_to(ROOT)}: {len(text.encode('utf-8'))} Б")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
