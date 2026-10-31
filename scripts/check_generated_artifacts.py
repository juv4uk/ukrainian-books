#!/usr/bin/env python3
"""Блокувати випадкове відстеження результатів книжкової верстки у Git."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

# Тут перевіряються тільки результати верстки у books/, не сторонні PDF
# в бібліографічних каталогах. EPUB буде окремим етапом погодження.
GENERATED_SUFFIXES = (
    ".pdf",
    ".aux",
    ".log",
    ".out",
    ".toc",
    ".fls",
    ".fdb_latexmk",
    ".synctex.gz",
    ".synctex",
    ".xdv",
    ".bbl",
    ".blg",
    ".idx",
    ".ilg",
    ".ind",
    ".nav",
    ".snm",
    ".vrb",
    ".bcf",
    ".run.xml",
)


def is_generated_book_artifact(path: str) -> bool:
    """Перевірити шлях у Git (роздільник завжди `/`)."""
    if not path.startswith("books/"):
        return False
    name = path.rsplit("/", 1)[-1]
    return bool(name) and name.casefold().endswith(GENERATED_SUFFIXES)


def tracked_paths(root: Path) -> list[str]:
    """Взяти лише відстежувані Git-шляхи; NUL зберігає пробіли й Unicode."""
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--cached", "-z", "--", "books/"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return [os.fsdecode(item) for item in result.stdout.split(b"\0") if item]


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    try:
        found = sorted(p for p in tracked_paths(root) if is_generated_book_artifact(p))
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"ПОМИЛКА: неможливо перевірити Git-індекс: {error}", file=sys.stderr)
        return 2
    if found:
        print("ПОМИЛКА: згенеровані файли верстки додано до Git:", file=sys.stderr)
        for path in found:
            print(f"  {path}", file=sys.stderr)
        print("Приберіть їх з індексу через git rm --cached; самі файли можна зберегти локально.", file=sys.stderr)
        return 1
    print("OK: у Git немає відстежуваних результатів книжкової верстки.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
