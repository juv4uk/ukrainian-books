#!/usr/bin/env python3
"""Структурний офлайновий контроль наукових сторінок, не рецензія й не аудит прав."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree as ET

VERSE = re.compile(r"^##\s+(\d+\.\d+)\s*$", re.MULTILINE)
FIELD = re.compile(r"^\*\*(Деванагарі|IAST|Українська транслітерація|Переклад|Коментар)\.\*\*[ \t]*(.*?)[ \t]*$", re.MULTILINE)
IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
PARALLEL = re.compile(r"^\*Українська паралель\s*\(([^)]*)\)\.\*\s*(.*)$", re.MULTILINE)
REFERENCE = re.compile(r"\[([^\]]{3,})\]\((https://[^\s)]+|[^\s():]+\.md(?:#[^\s)]*)?)\)")
LABELS = ["Деванагарі", "IAST", "Українська транслітерація", "Переклад", "Коментар"]
DEVANAGARI = re.compile(r"[\u0900-\u097F]")
CYRILLIC = re.compile(r"[А-Яа-яІіЇїЄєҐґ]")
LATIN = re.compile(r"[A-Za-z]")
FORBIDDEN_TAGS = {"script", "foreignObject", "image", "iframe", "object", "embed"}


def svg_errors(svg: Path) -> list[str]:
    """Лише технічна SVG-безпека; ані авторство, ані дозвіл це не доводить."""
    try:
        root = ET.parse(svg).getroot()
    except (ET.ParseError, OSError) as exc:
        return [f"SVG не читається: {exc}"]
    if root.tag.split("}")[-1] != "svg":
        return ["Кореневий елемент зображення має бути svg"]
    errors = []
    for node in root.iter():
        name = node.tag.split("}")[-1]
        if name in FORBIDDEN_TAGS:
            errors.append(f"SVG містить заборонений елемент {name}")
        for attr, val in node.attrib.items():
            attr_name = attr.split("}")[-1].lower()
            if attr_name.startswith("on"):
                errors.append(f"SVG містить атрибут обробника події {attr_name}")
            if attr_name == "href" and not val.startswith("#"):
                errors.append("SVG містить зовнішнє або вбудоване посилання href")
            if re.search(r"url\(\s*['\"]?(?!#)[^)]", val, flags=re.IGNORECASE):
                errors.append("SVG містить посилання на ресурс поза локальною графікою")
    return errors


def check_page(path: Path, repo_root: Path) -> list[str]:
    """Повертає діагностичні повідомлення, не редагуючи файлів."""
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return [f"{path}: файл не читається: {exc}"]
    headers = list(VERSE.finditer(content))
    if not headers:
        return [f"{path}: немає жодного заголовка вірша формату '## 6.1'"]
    errors = []
    seen = set()
    for idx, header in enumerate(headers):
        verse = header.group(1)
        prefix = f"{path}:{verse}"
        if verse in seen:
            errors.append(f"{prefix}: повторений номер вірша")
        seen.add(verse)
        end = headers[idx + 1].start() if idx + 1 < len(headers) else len(content)
        chunk = content[header.end():end]
        fields = list(FIELD.finditer(chunk))
        names = [m.group(1) for m in fields]
        if names != LABELS:
            errors.append(f"{prefix}: очікувані шари у порядку {', '.join(LABELS)}; знайдено {', '.join(names)}")
        for item in fields:
            if not item.group(2).strip():
                errors.append(f"{prefix}: порожній шар «{item.group(1)}»")
        values = {m.group(1): m.group(2).strip() for m in fields}
        if "Деванагарі" in values and not DEVANAGARI.search(values["Деванагарі"]):
            errors.append(f"{prefix}: шар деванагарі не містить письма деванагарі")
        if "IAST" in values and (not LATIN.search(values["IAST"]) or CYRILLIC.search(values["IAST"])):
            errors.append(f"{prefix}: IAST має бути латиницею без кирилиці")
        if "Українська транслітерація" in values:
            v = values["Українська транслітерація"]
            if not CYRILLIC.search(v) or LATIN.search(v):
                errors.append(f"{prefix}: українська транслітерація має бути кирилицею без латинських літер")
        for note in PARALLEL.finditer(chunk):
            label, body = note.groups()
            if "наша асоціація" not in label.lower() and "наша паралель" not in label.lower():
                errors.append(f"{prefix}: українську паралель треба назвати авторською асоціацією")
            if not REFERENCE.search(body):
                errors.append(f"{prefix}: українська паралель не має названого твору з посиланням")
        for alt, raw in IMAGE.findall(chunk):
            if len(alt.strip()) < 8:
                errors.append(f"{prefix}: потрібен змістовний підпис ілюстрації")
            src = unquote(raw.split("#", 1)[0])
            if "?" in src or "//" in src or re.match(r"^[A-Za-z][\w+.-]*:", src):
                errors.append(f"{prefix}: лише локальні SVG без URL-параметрів")
                continue
            target = (path.parent / src).resolve()
            try:
                target.relative_to(repo_root.resolve())
            except ValueError:
                errors.append(f"{prefix}: шлях ілюстрації виходить за межі репозиторію")
                continue
            if target.suffix.lower() != ".svg" or not target.is_file():
                errors.append(f"{prefix}: ілюстрація має бути наявним локальним SVG: {src}")
                continue
            errors.extend(f"{prefix}: {msg}" for msg in svg_errors(target))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pages", type=Path, nargs="+", help="Одна або кілька наукових Markdown-сторінок")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Корінь репозиторію для локальних SVG")
    args = parser.parse_args(argv)
    errors = [message for path in args.pages for message in check_page(path, args.root)]
    print(json.dumps({"status": "failed" if errors else "ok", "pages": len(args.pages), "errors": errors}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
