#!/usr/bin/env python3
"""Офлайнова звірка довідкових Markdown-посилань із локальними цілями.

Не перевіряє зовнішні ресурси, якість джерел чи авторські права.
Звичайні inline-посилання перевіряє scripts/check_project.py.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DEFINITION = re.compile(r"^ {0,3}\[([^\]\n]+)\]:[ \t]*(.*)$")
REFERENCE = re.compile(r"!?\[([^\]\n]+)\]\[([^\]\n]*)\]")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(?:[^\n]*)$")
INLINE_CODE = re.compile(r"(`+)(.*?)\1")


def normalized(label: str) -> str:
    """Markdown-мітки нечутливі до регістру й повторів пропусків."""
    return " ".join(label.split()).casefold()


def content_lines(text: str):
    """Пропустити потрійні fenced code blocks і прості inline code spans."""
    marker = ""
    marker_size = 0
    for number, original in enumerate(text.splitlines(), 1):
        match = FENCE.match(original)
        if match:
            fence = match.group(1)
            if not marker:
                marker, marker_size = fence[0], len(fence)
                continue
            if fence[0] == marker and len(fence) >= marker_size and not original[len(fence):].strip():
                marker, marker_size = "", 0
                continue
        if marker:
            continue
        yield number, INLINE_CODE.sub("", original)


def destination(definition: str) -> str:
    """Витягнути адресу з визначення в кутових дужках або без них."""
    value = definition.strip()
    if value.startswith("<"):
        end = value.find(">")
        return value[1:end] if end > 0 else ""
    return value.split(maxsplit=1)[0] if value else ""


def check_file(path: Path, root: Path) -> list[str]:
    errors: list[str] = []
    root = root.resolve()
    relative = path.relative_to(root)
    definitions: dict[str, tuple[str, int]] = {}
    uses: list[tuple[str, int]] = []
    for line_number, line in content_lines(path.read_text(encoding="utf-8")):
        match = DEFINITION.match(line)
        if match and not match.group(1).startswith("^"):
            label = normalized(match.group(1))
            if label in definitions:
                errors.append(f"{relative}:{line_number}: повторена мітка [{match.group(1)}]")
            else:
                definitions[label] = (destination(match.group(2)), line_number)
            continue
        for found in REFERENCE.finditer(line):
            label = normalized(found.group(2) or found.group(1))
            if label and not label.startswith("^"):
                uses.append((label, line_number))

    for label, line_number in uses:
        if label not in definitions:
            errors.append(f"{relative}:{line_number}: невизначена мітка [{label}]")
    for label, (target, line_number) in definitions.items():
        if not target:
            errors.append(f"{relative}:{line_number}: порожня ціль [{label}]")
            continue
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or target.startswith(("#", "//")):
            continue
        name = unquote(parsed.path)
        if not name:
            continue
        candidate = (path.parent / name).resolve()
        if not candidate.is_relative_to(root):
            errors.append(f"{relative}:{line_number}: вихід поза репозиторій [{label}] → {target}")
        elif not candidate.exists():
            errors.append(f"{relative}:{line_number}: відсутня локальна ціль [{label}] → {target}")
    return errors


def check_tree(root: Path) -> tuple[int, list[str]]:
    root = root.resolve()
    files = sorted(path for path in root.rglob("*.md") if ".git" not in path.parts)
    errors: list[str] = []
    for path in files:
        errors.extend(check_file(path, root))
    return len(files), errors


def main() -> int:
    count, errors = check_tree(ROOT)
    for message in errors:
        print(message)
    print(f"Довідкові Markdown-посилання: {count} файлів, {len(errors)} помилок")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
