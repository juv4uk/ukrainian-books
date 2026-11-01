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
# Локальні посилання та зображення мають однаково існувати у дереві.
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def check_card_json_syntax(root: Path) -> list[str]:
    """Загальний гейт не повинен пропускати зламані JSON-картки.

    Повну редакторську схему, унікальність ключів та права перевіряють
    окремі інструменти. Тут перевіряємо лише існування коректного JSON.
    """
    errors: list[str] = []
    cards = root / "editorial" / "cards"
    if cards.is_symlink():
        return ["editorial/cards: символічне посилання заборонено"]
    if cards.exists() and not cards.is_dir():
        return ["editorial/cards: очікується каталог"]
    if not cards.is_dir():
        return errors

    for path in sorted(cards.glob("*.json")):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            errors.append(f"{rel}: символічне посилання заборонено")
            continue
        if not path.is_file():
            errors.append(f"{rel}: очікується JSON-файл")
            continue
        try:
            json.loads(path.read_text(encoding="utf-8", errors="strict"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"{rel}: некоректний JSON або UTF-8: {exc}")
    return errors


def check_scholarly_pages(root: Path) -> list[str]:
    """Структурна перевірка наукових сторінок книжки — обовʼязковий гейт.

    Раніше `scripts/check_scholarly_pages.py` існував, але його не викликав
    ніхто: перевірка вимагала маркер `**Коментар.**` і шар `**IAST.**`, а
    генератор писав `**Науковий коментар.**` без IAST. Тепер, коли боки
    зведено (канон — `docs/FORMAT_V2.md`), перевірка входить до гейту: далі
    вона не може знову тихо померти.
    """
    package_root = Path(__file__).resolve().parents[1]
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))
    from scripts.check_scholarly_pages import check_page

    errors: list[str] = []
    books = root / "books"
    if not books.is_dir():
        return errors
    for page in sorted(books.glob("*/rozdil-*-naukove.md")):
        if page.is_symlink() or not page.is_file():
            errors.append(f"{page.name}: очікується звичайний Markdown-файл")
            continue
        rel = page.relative_to(root).as_posix()
        for message in check_page(page, root):
            errors.append(message.replace(str(page), rel, 1))
    return errors


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

    # Помилка синтаксису картки має провалювати також загальний CI-гейт.
    errors.extend(check_card_json_syntax(ROOT))

    # Наукові сторінки: шари, паралелі та безпека SVG (той самий чек, що й
    # `scripts/check_scholarly_pages.py`, лише по всіх главах одразу).
    errors.extend(check_scholarly_pages(ROOT))

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
