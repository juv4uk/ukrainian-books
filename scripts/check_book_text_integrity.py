#!/usr/bin/env python3
"""РЕД-05: виявити технічні пошкодження Unicode у власних книжкових текстах."""

from __future__ import annotations

import argparse
import json
import unicodedata
from pathlib import Path

SUFFIXES = frozenset({".tex", ".md", ".txt", ".bib", ".sty", ".cls"})
INVISIBLE = frozenset({0x200B, 0x2060, 0xFEFF})
BIDI = frozenset({0x061C, 0x200E, 0x200F}) | frozenset(range(0x202A, 0x202F)) | frozenset(range(0x2066, 0x206A))
MAX_PER_FILE = 25


def script_of(letter: str) -> str | None:
    """Літерна писемність для зіставлення з прилеглим комбінувальним знаком."""
    if not unicodedata.category(letter).startswith("L"):
        return None
    name = unicodedata.name(letter, "")
    if name.startswith("CYRILLIC "):
        return "CYRILLIC"
    if name.startswith("LATIN "):
        return "LATIN"
    return None


def scan_text(text: str) -> list[dict]:
    """Знайти лише технічні артефакти; не оцінювати орфографію чи зміст."""
    findings: list[dict] = []
    line, column = 1, 1
    base_script = None
    for char in text:
        number = ord(char)
        category = unicodedata.category(char)
        name = unicodedata.name(char, "НЕВІДОМИЙ СИМВОЛ")
        reason = None
        if number == 0xFFFD:
            reason = "символ заміни Unicode: імовірно втрачено вихідні байти"
        elif (number < 0x20 and char not in "\n\r\t") or 0x7F <= number <= 0x9F:
            reason = "неприпустимий керувальний символ"
        elif number in INVISIBLE or number in BIDI:
            reason = "невидимий символ або керування напрямком письма"
        elif category.startswith("M") and name.split(" ", 1)[0] in {"HEBREW", "ARABIC"} and base_script in {"CYRILLIC", "LATIN"}:
            reason = "комбінувальний знак іншої писемності після кирилиці або латинки"

        if reason:
            findings.append({
                "line": line, "column": column, "codepoint": f"U+{number:04X}",
                "reason": reason,
            })
            if len(findings) >= MAX_PER_FILE:
                break

        if category.startswith("L"):
            base_script = script_of(char)
        elif not category.startswith("M"):
            base_script = None

        if char == "\n":
            line, column = line + 1, 1
        else:
            column += 1
    return findings


def audit(root: Path) -> dict:
    """Перевіряти лише файли власних видань; не переходити за симлінками."""
    books = root / "books"
    errors: list[dict] = []
    examined = 0
    if books.is_dir():
        for path in sorted(books.rglob("*")):
            if path.is_symlink() or not path.is_file() or path.suffix.lower() not in SUFFIXES:
                continue
            examined += 1
            rel = path.relative_to(root).as_posix()
            try:
                content = path.read_text(encoding="utf-8", errors="strict")
            except UnicodeDecodeError as exc:
                errors.append({"path": rel, "codepoint": "UTF-8", "reason": f"некоректні байти UTF-8 на позиції {exc.start}"})
                continue
            for error in scan_text(content):
                errors.append({"path": rel, **error})
    return {
        "status": "ok" if not errors else "failed",
        "scanned_files": examined,
        "errors": errors,
        "scope": "Лише books/**; це не орфографічна, наукова чи правова перевірка",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = audit(args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
