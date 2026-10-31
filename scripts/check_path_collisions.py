#!/usr/bin/env python3
"""Блокувати Git-шляхи, несумісні з файловими системами різного регістру.

Виявляє колізії Unicode NFC + casefold у файлах і каталогах. Перевіряє
лише шляхи з Git-індексу, а не локальні тимчасові файли чи кеш збірки.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import unicodedata
from pathlib import Path


def key_component(component: str) -> str:
    """Нормалізувати одну компоненту шляху для консервативної звірки."""
    return unicodedata.normalize("NFC", component).casefold()


def find_collisions(paths: list[str]) -> list[tuple[str, str]]:
    """Знайти конфліктні написання будь-якого префікса шляху.

    Врахування префіксів виявляє і різний регістр назви каталогу,
    навіть якщо назви самих файлів відрізняються.
    """
    observed: dict[tuple[str, ...], str] = {}
    conflicts: set[tuple[str, str]] = set()
    for path in sorted(set(paths)):
        components = path.split("/")
        for depth in range(1, len(components) + 1):
            original = "/".join(components[:depth])
            normalized = tuple(key_component(part) for part in components[:depth])
            previous = observed.setdefault(normalized, original)
            if previous != original:
                conflicts.add(tuple(sorted((previous, original))))
    return sorted(conflicts)


def tracked_paths(root: Path) -> list[str]:
    """Прочитати точні Git-шляхи з індексу, без quotePath і без shell."""
    completed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--cached"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return [entry.decode("utf-8", errors="surrogateescape")
            for entry in completed.stdout.split(b"\0") if entry]


def run(root: Path) -> int:
    try:
        paths = tracked_paths(root)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"ПОМИЛКА: не вдалося прочитати Git-індекс: {exc}", file=sys.stderr)
        return 2

    if not paths:
        print("ПОМИЛКА: Git-індекс не містить жодного файлу", file=sys.stderr)
        return 2

    collisions = find_collisions(paths)
    if collisions:
        print(f"ПОМИЛКА: виявлено {len(collisions)} колізій Git-шляхів (NFC + casefold):", file=sys.stderr)
        for left, right in collisions:
            print(f"  {left!r}  <>  {right!r}", file=sys.stderr)
        return 1

    print(f"Гаразд: {len(paths)} Git-файлів, колізій імен немає (NFC + casefold)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    return run(args.root)


if __name__ == "__main__":
    raise SystemExit(main())
