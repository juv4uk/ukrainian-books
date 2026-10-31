#!/usr/bin/env python3
"""Перевірка структури, власної ліцензії та походження матеріалів."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "README.md", "LICENSE", "VOLNOST.md", "CONTRIBUTING.md",
    "COPYRIGHT_AND_SOURCES.md", "docs/START.md",
    "docs/PROVENANCE_TEMPLATE.md", "tasks/ROADMAP.md", "tasks/ISSUES.json",
    "research/ashtavakra/bibliography.md",
    "research/ashtavakra/verses-1-1-to-1-5.md",
    ".github/workflows/quality.yml",
    ".github/workflows/build-books.yml",
)
FORBIDDEN = (
    "LICENSE-CODE", "ashtavakra gita", "da perfeicao de ser",
    "o caminho da libertacao", "pura graca", "livros", ".gitmodules",
)
LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


def run() -> int:
    errors: list[str] = []
    for rel in REQUIRED:
        if not (ROOT / rel).is_file():
            errors.append(f"Відсутній обов'язковий файл: {rel}")
    for rel in FORBIDDEN:
        if (ROOT / rel).exists():
            errors.append(f"Сторонній матеріал або інша ліцензія: {rel}")

    license_path = ROOT / "LICENSE"
    copy_path = ROOT / "VOLNOST.md"
    if license_path.is_file() and copy_path.is_file():
        license_text = license_path.read_text(encoding="utf-8")
        copy_text = copy_path.read_text(encoding="utf-8")
        if license_text != copy_text:
            errors.append("LICENSE та VOLNOST.md мають бути буквально однакові")
        if not license_text.startswith("ВОЛЬНІСТЬ\n\n"):
            errors.append("Неправильний заголовок канонічної ліцензії")

    book_root = ROOT / "books"
    if book_root.is_dir():
        for folder in book_root.iterdir():
            if folder.is_dir() and not (folder / "PROVENANCE.md").is_file():
                errors.append(f"Немає паспорта походження: {folder.name}")

    for file in list(ROOT.rglob("*.tex")) + list(ROOT.rglob("*.pdf")):
        if ".git" in file.parts:
            continue
        rel = file.relative_to(ROOT)
        if len(rel.parts) < 3 or rel.parts[0] != "books":
            errors.append(f"Сторонній книжковий файл поза books/: {rel}")
        elif not (ROOT / "books" / rel.parts[1] / "PROVENANCE.md").is_file():
            errors.append(f"Видання без паспорта прав: {rel}")

    markdown = [f for f in ROOT.rglob("*.md") if ".git" not in f.parts]
    for path in markdown:
        rel = path.relative_to(ROOT)
        data = path.read_text(encoding="utf-8")
        if not data.strip():
            errors.append(f"Порожній документ: {rel}")
        for link in LINK.findall(data):
            target = unquote(link.split("#", 1)[0]).strip()
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            candidate = (path.parent / target).resolve()
            if not candidate.is_relative_to(ROOT) or not candidate.exists():
                errors.append(f"Некоректне посилання: {rel} → {link}")

    try:
        issues = json.loads((ROOT / "tasks/ISSUES.json").read_text(encoding="utf-8"))
        ids = [item["code"] for item in issues]
        if len(ids) != len(set(ids)):
            errors.append("Повторені коди Issues")
    except (OSError, ValueError, KeyError, TypeError) as e:
        errors.append(f"Недійсний реєстр Issues: {e}")

    result = {"status": "ok" if not errors else "failed",
              "markdown_files": len(markdown), "errors": errors}
    report = ROOT / "reports" / "checks.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(run())
