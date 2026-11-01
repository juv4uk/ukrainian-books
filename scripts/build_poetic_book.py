#!/usr/bin/env python3
"""Збирає верстку поетичного перекладу «Аштавакра-ґіти» з розділів у Markdown.

Джерело — `books/ashtavakra-gita/poetychnyi/rozdil-N.md`. Це **наш власний**
поетичний переклад; жодних чужих транскрипцій чи перекладів скрипт не переносить.

Вихід — `books/ashtavakra-poetychnyi/generated/poems.tex`, який підключає
`books/ashtavakra-poetychnyi/main.tex`.

Запуск:
    python3 scripts/build_poetic_book.py           # згенерувати
    python3 scripts/build_poetic_book.py --check   # лише перевірити свіжість
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "books" / "ashtavakra-gita" / "poetychnyi"
BOOK = ROOT / "books" / "ashtavakra-poetychnyi"
TARGET = BOOK / "generated" / "poems.tex"

CHAPTER_HEAD = re.compile(r"^#\s+Аштавакра-ґіта\.\s*Розділ\s+(\d+)", re.IGNORECASE)
VERSE_HEAD = re.compile(r"^##\s+(\d+\.\d+)\s*$")

SPECIAL = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def esc(text: str) -> str:
    """Екранує керівні символи LaTeX, зберігаючи українську типографіку."""
    return "".join(SPECIAL.get(ch, ch) for ch in text)


def chapters() -> list[tuple[int, Path]]:
    found = []
    for path in SOURCE.glob("rozdil-*.md"):
        m = re.match(r"rozdil-(\d+)\.md$", path.name)
        if m:
            found.append((int(m.group(1)), path))
    return sorted(found)


def render_chapter(number: int, path: Path) -> str:
    out = [r"\poemchapter{%d}" % number]
    block: list[str] = []
    mode = "verse"

    def flush() -> None:
        if not block:
            return
        if mode == "note":
            out.append(r"\poemnote{%s}" % esc(" ".join(block)))
        else:
            out.append(r"\poemstanza{%s}" % r" \\ ".join(esc(line) for line in block))
        block.clear()

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line.strip():
            flush()
            continue
        if CHAPTER_HEAD.match(line):
            continue
        if line.startswith(">"):
            continue
        m = VERSE_HEAD.match(line)
        if m:
            flush()
            mode = "verse"
            out.append(r"\poemverse{%s}" % m.group(1))
            continue
        if line.startswith("## "):
            flush()
            mode = "note"
            out.append(r"\poemsection{%s}" % esc(line[3:].strip()))
            continue
        if line.startswith("#"):
            # Заголовок розділу або підзаголовок книги — не текст строфи.
            continue
        block.append(line.strip())
    flush()
    return "\n".join(out) + "\n"


def render() -> str:
    parts = [
        "% ЗГЕНЕРОВАНО scripts/build_poetic_book.py — не редагувати вручну.",
        "% Джерело: books/ashtavakra-gita/poetychnyi/rozdil-N.md",
        "% Це власний поетичний переклад; чужих транскрипцій тут немає.",
        "",
    ]
    for number, path in chapters():
        parts.append(render_chapter(number, path))
    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    text = render()
    found = chapters()
    stale = not TARGET.is_file() or TARGET.read_text(encoding="utf-8") != text
    manifest = {
        "chapters": [n for n, _ in found],
        "generated_chars": len(text),
        "stale": stale,
    }
    if not args.check:
        TARGET.parent.mkdir(parents=True, exist_ok=True)
        TARGET.write_text(text, encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 1 if (args.check and stale) else 0


if __name__ == "__main__":
    sys.exit(main())
