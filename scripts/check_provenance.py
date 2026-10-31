#!/usr/bin/env python3
"""Машинна перевірка форми дозволів: НЕ юридичний висновок."""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

FIELDS = (
 "Твір / назва оригіналу",
 "Автор первісного твору",
 "Джерельне видання / URL / рік",
 "Мова джерела, прямий переклад чи через посередника",
 "Автор українського перекладу",
 "Правова підстава перекладу і публікації",
 "Документ / URL, що підтверджує права",
 "Дозвіл на PDF / EPUB / редагування / подальше поширення",
 "Авторський внесок, до якого застосовано «ВОЛЬНІСТЬ»",
 "Чужі матеріали й їхні окремі умови (якщо є)",
 "Рецензент, дата перевірки",
 "Статус",
)
FIELD_LINE = re.compile(r"^\s*[-*]\s*\*\*(.+?):\*\*\s*(.*?)\s*$")
PLACEHOLDER = re.compile(
 r"^(?:todo|tbd|уточнити|невідомо|не встановлено|не перевірено|"
 r"очікує|потрібно|поки|відсутній|немає)(?:\b|$)", re.IGNORECASE
)
DATE = re.compile(r"\b(?:20\d\d-\d\d-\d\d|\d\d\.\d\d\.20\d\d)\b")
HTTPS = re.compile(r"https://[^\s)>\]]+")


def clean(raw: str) -> str:
    return raw.strip(" *_").strip()


def unfinished(value: str, allow_none: bool = False) -> bool:
    val = clean(value).casefold()
    if allow_none and val in ("немає", "відсутні", "не використовувалися"):
        return False
    return not val or val in ("—", "-", "?", "…", "...") or bool(PLACEHOLDER.match(val))


def parse_passport(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = FIELD_LINE.match(line)
        if m:
            name = m.group(1).strip()
            # Повторене контрактне поле не можна стиха перекрити пізнішим
            # рядком: так можна приховати суперечливе рішення про права.
            if name in FIELDS and name in values:
                raise ValueError(f"повторене поле «{name}» у PROVENANCE.md")
            values[name] = m.group(2).strip()
    return values


def explicit_permissions(value: str) -> bool:
    text = clean(value).casefold()
    for label in ("pdf", "epub", "редагування", "поширення"):
        if not re.search(
            rf"(?:^|[;,\n])\s*{label}\s*:\s*(?:так|дозволено)(?:\b|$)",
            text,
        ):
            return False
    return True


def audit(root: Path) -> dict:
    books = root / "books"
    errors: list[str] = []
    records: list[dict] = []
    warning = "Формальна перевірка НЕ підтверджує юридичну чинність дозволів"
    # Навіть пошкоджений симлінк не можна вважати відсутнім каталогом.
    if books.is_symlink():
        return {"status": "failed", "books": records,
                "errors": ["books: символічне посилання заборонено"],
                "warning": warning}
    if not books.exists():
        return {"status": "ok", "books": records, "errors": errors,
                "warning": warning + "; у репозиторії поки немає книг"}
    if not books.is_dir():
        return {"status": "failed", "books": records,
                "errors": ["books не є каталогом"], "warning": warning}

    for directory in sorted(books.iterdir()):
        # Допускаємо лише звичайний службовий .gitkeep, а не його симлінк.
        if (directory.name == ".gitkeep" and directory.is_file()
                and not directory.is_symlink()):
            continue
        if directory.is_symlink():
            errors.append(f"books/{directory.name}: символічне посилання заборонено")
            continue
        if not directory.is_dir():
            errors.append(f"Некоректний запис у books/: {directory.name}")
            continue
        base = directory.name
        passport = directory / "PROVENANCE.md"
        # Не розіменовуємо симлінки (також пошкоджені та на каталоги).
        # Перевіряємо всі вкладені записи, а не лише is_file().
        entries = list(directory.rglob("*"))
        links = [p for p in entries if p.is_symlink()]
        materials = [
            p for p in entries
            if p.is_file() and p != passport and p.name != ".gitkeep"
        ]
        record = {"book": base, "files": len(materials), "state": "metadata-only"}
        records.append(record)
        if links:
            errors.extend(
                f"{base}: символічне посилання заборонено: {p.relative_to(root)}"
                for p in links
            )
            record["state"] = "blocked"
            continue
        if not passport.is_file() or passport.is_symlink():
            errors.append(f"{base}: немає звичайного PROVENANCE.md")
            record["state"] = "blocked"
            continue

        # Metadata-only draft may exist. Any material in a public repository
        # requires an approved and fully completed provenance passport.
        if not materials:
            continue
        try:
            values = parse_passport(passport)
        except ValueError as exc:
            errors.append(f"{base}: {exc}")
            record["state"] = "blocked"
            continue
        for name in FIELDS:
            if name not in values or unfinished(
                values.get(name, ""),
                allow_none=name == "Чужі матеріали й їхні окремі умови (якщо є)",
            ):
                errors.append(f"{base}: незаповнене поле «{name}»")
        if clean(values.get("Статус", "")).casefold() != "дозволено до публікації":
            errors.append(f"{base}: статус не дозволяє публікацію")
        if not HTTPS.search(values.get("Документ / URL, що підтверджує права", "")):
            errors.append(f"{base}: немає HTTPS-посилання на докази прав")
        if not explicit_permissions(values.get(
            "Дозвіл на PDF / EPUB / редагування / подальше поширення", ""
        )):
            errors.append(f"{base}: не підтверджені окремі PDF/EPUB/редагування/поширення")
        if not DATE.search(values.get("Рецензент, дата перевірки", "")):
            errors.append(f"{base}: немає дати перевірки")
        record["state"] = "blocked" if any(
            err.startswith(base + ":") for err in errors
        ) else "metadata-complete"

    return {"status": "failed" if errors else "ok", "books": records,
            "errors": errors, "warning": warning}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path,
                        default=Path(__file__).resolve().parents[1])
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = audit(args.root)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    print(payload)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload, encoding="utf-8")
    return int(bool(result["errors"]))


if __name__ == "__main__":
    sys.exit(main())
