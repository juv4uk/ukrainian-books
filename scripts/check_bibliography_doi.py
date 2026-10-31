#!/usr/bin/env python3
"""Офлайн-перевірка DOI-адрес у бібліографічних Markdown-посиланнях.

Не перевіряє наявності статей, метаданих, наукової якості чи авторських прав.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

LINK = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)\s]+)\)")
LABEL = re.compile(r"\bDOI\s*:?\s*(10\.\d{4,9}/[^\s\]]+)", re.I)
DOI = re.compile(r"^10\.\d{4,9}/[^\s<>\[\]?#]+$", re.I)
REFERENCE = re.compile(r"(?<!!)\[([^\]\n]+)\]\[([^\]\n]*)\]")
DEFINITION = re.compile(r"^ {0,3}\[([^\]\n]+)\]:[ \t]*(.*)$", re.M)


def normalize_label(label: str) -> str:
    """У довідкових Markdown-мітках неважливі регістр і повторні пробіли."""
    return " ".join(label.split()).casefold()


def definition_target(value: str) -> str:
    """Адреса з визначення, зокрема <URL> з необов'язковим заголовком."""
    value = value.strip()
    if value.startswith("<"):
        end = value.find(">")
        return value[1:end] if end >= 0 else ""
    return value.split(maxsplit=1)[0] if value else ""



def inspect(source: str, filename: str) -> tuple[int, list[str]]:
    """Однакові правила для inline і довідкових DOI-адрес Markdown."""
    checked, errors = 0, []
    definitions: dict[str, str] = {}
    for match in DEFINITION.finditer(source):
        definitions.setdefault(
            normalize_label(match.group(1)), definition_target(match.group(2))
        )

    candidates: list[tuple[int, str, str]] = [
        (match.start(), match.group(1), match.group(2))
        for match in LINK.finditer(source)
    ]
    for match in REFERENCE.finditer(source):
        label, reference = match.groups()
        key = normalize_label(reference or label)
        target = definitions.get(key)
        if target is None:
            # Невизначені звичайні мітки контролює check_reference_links.py;
            # заявлений DOI не можна пропускати як нібито перевірений.
            if LABEL.search(label):
                checked += 1
                place = f"{filename}:{source.count(chr(10), 0, match.start()) + 1}"
                errors.append(f"{place}: невизначена довідкова DOI-мітка [{key}]")
            continue
        candidates.append((match.start(), label, target))

    for offset, label, target in sorted(candidates):
        visible = LABEL.search(label)
        try:
            url = urlsplit(target)
            host, port = url.hostname, url.port
        except ValueError:
            url, host, port = None, None, None
        if host not in {"doi.org", "dx.doi.org"} and not visible:
            continue
        checked += 1
        place = f"{filename}:{source.count(chr(10), 0, offset) + 1}"
        if (url is None or url.scheme != "https" or host != "doi.org"
                or port is not None or url.username or url.password
                or url.query or url.fragment):
            errors.append(f"{place}: потрібна адреса https://doi.org/ без параметрів")
            continue
        actual = unquote(url.path.lstrip("/"))
        if not DOI.fullmatch(actual):
            errors.append(f"{place}: некоректний DOI в адресі {actual!r}")
        if visible and visible.group(1).casefold() != actual.casefold():
            errors.append(f"{place}: DOI в підписі не збігається з адресою")
    return checked, errors

def audit(root: Path) -> dict:
    folder = root / "research/ashtavakra"
    files = sorted(folder.glob("bibliography*.md"))
    checked, errors = 0, []
    if not files:
        errors.append("Не знайдено research/ashtavakra/bibliography*.md")
    for file in files:
        try:
            data = file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"{file.name}: помилка читання UTF-8: {exc}")
            continue
        found, issues = inspect(data, file.relative_to(root).as_posix())
        checked += found
        errors.extend(issues)
    return {"status": "failed" if errors else "ok", "files": len(files),
            "doi_links": checked, "errors": errors,
            "scope": "Лише синтаксис; DOI-реєстр і права не перевіряються"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    result = audit(parser.parse_args().root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
