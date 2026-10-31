#!/usr/bin/env python3
"""Офлайновий спостережний аудит локальних фрагментів Markdown.

Без мережі. За замовчуванням повідомляє про підозрілі якорі, але не
зупиняє CI: наближена модель заголовків не замінює рендерер GitHub.
Для локальної перевірки з ненульовим кодом існує --strict.
"""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
FENCE = re.compile(r"^ {0,3}(\x60{3,}|~{3,})(.*)$")
ATX = re.compile(r"^ {0,3}#{1,6}[ \t]+(.+?)\s*$")
SETEXT = re.compile(r"^ {0,3}(?:=+|-+)[ \t]*$")
INLINE = re.compile(
    r"!?\[[^\]\n]*\]\(\s*(?:<([^>\n]+)>|([^\s)\n]+))(?:\s+[^)\n]*)?\)"
)
DEFINITION = re.compile(r"^ {0,3}\[([^\]\n]+)\]:[ \t]*(?:<([^>\n]+)>|(\S+))")
REFERENCE = re.compile(r"!?\[([^\]\n]+)\]\[([^\]\n]*)\]")
INLINE_CODE = re.compile(r"(\x60+)(.*?)\1")


def content_lines(data: str):
    """Рядки поза огородженими блоками коду."""
    marker = ""
    marker_size = 0
    for number, line in enumerate(data.splitlines(), 1):
        match = FENCE.match(line)
        if match:
            fence, rest = match.groups()
            if not marker:
                marker, marker_size = fence[0], len(fence)
                continue
            if fence[0] == marker and len(fence) >= marker_size and not rest.strip():
                marker, marker_size = "", 0
                continue
        if not marker:
            yield number, line


def normalized_label(value: str) -> str:
    return " ".join(value.split()).casefold()


def plain_heading(value: str) -> str:
    """Приблизно вилучити Markdown-розмітку без зміни українських літер."""
    value = re.sub(r"\s+#+\s*$", "", value)
    value = re.sub(r"!\[([^\]]+)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"\[([^\]]+)\]\[[^\]]*\]", r"\1", value)
    value = re.sub(r"\x60+([^\x60]+)\x60+", r"\1", value)
    value = re.sub(r"<[^>]+>", "", value)
    return html.unescape(value.replace("*", "").replace("~", "")).strip()


def slug(value: str) -> str:
    """Наближення до якорів заголовків GitHub Markdown (не повний парсер)."""
    plain = plain_heading(value).lower()
    plain = re.sub(r"[^\w\s-]", "", plain, flags=re.UNICODE)
    return re.sub(r"\s+", "-", plain.strip())


def heading_anchors(path: Path) -> set[str]:
    used: dict[str, int] = {}
    result: set[str] = set()
    previous: str | None = None

    def add(value: str) -> None:
        base = slug(value)
        if not base:
            return
        number = used.get(base, 0)
        used[base] = number + 1
        result.add(base if number == 0 else f"{base}-{number}")

    for _, line in content_lines(path.read_text(encoding="utf-8")):
        atx = ATX.match(line)
        if atx:
            add(atx.group(1))
            previous = None
        elif SETEXT.match(line) and previous:
            add(previous)
            previous = None
        else:
            candidate = line.strip()
            previous = (
                candidate if candidate and not candidate.startswith(
                    ("[", ">", "-", "*", "+", "|", "#")
                ) else None
            )
    return result


def local_target(root: Path, source: Path, url: str) -> tuple[Path, str] | None:
    """Лише локальні Markdown-шляхи з непорожнім фрагментом."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    if parts.scheme or parts.netloc or not parts.fragment:
        return None
    if parts.path.startswith("/"):
        return None  # Кореневий URL сайту не обов'язково є шляхом репозиторію.
    path = unquote(parts.path)
    if path and not path.lower().endswith((".md", ".markdown")):
        return None
    target = (source.parent / path).resolve() if path else source.resolve()
    if not target.is_relative_to(root.resolve()) or not target.is_file():
        return None  # Існування файлів перевіряють інші валідатори.
    return target, unquote(parts.fragment)


def check_file(path: Path, root: Path,
               cache: dict[Path, set[str]] | None = None) -> list[str]:
    """Повернути підозрілі локальні якорі з номерами рядків."""
    root = root.resolve()
    cache = {} if cache is None else cache
    lines = list(content_lines(path.read_text(encoding="utf-8")))
    definitions: dict[str, str] = {}
    for _, line in lines:
        no_code = INLINE_CODE.sub("", line)
        match = DEFINITION.match(no_code)
        if match:
            definitions[normalized_label(match.group(1))] = (
                match.group(2) or match.group(3)
            )

    errors: list[str] = []
    for number, line in lines:
        no_code = INLINE_CODE.sub("", line)
        targets = [m.group(1) or m.group(2) for m in INLINE.finditer(no_code)]
        for match in REFERENCE.finditer(no_code):
            label = normalized_label(match.group(2) or match.group(1))
            if label in definitions:
                targets.append(definitions[label])

        for url in targets:
            value = local_target(root, path, url)
            if value is None:
                continue
            target, fragment = value
            if target not in cache:
                cache[target] = heading_anchors(target)
            if fragment not in cache[target]:
                relative = path.relative_to(root)
                name = target.relative_to(root)
                errors.append(
                    f"{relative}:{number}: невідомий Markdown-якір "
                    f"#{fragment} у {name}"
                )
    return errors


def check_tree(root: Path) -> tuple[int, list[str]]:
    root = root.resolve()
    paths = sorted(
        path for path in root.rglob("*.md") if ".git" not in path.parts
    )
    cache: dict[Path, set[str]] = {}
    errors: list[str] = []
    for path in paths:
        errors.extend(check_file(path, root, cache))
    return len(paths), errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--strict", action="store_true",
                        help="завершуватися з кодом 1 при підозрілих якорях")
    args = parser.parse_args()
    count, errors = check_tree(args.root)
    for error in errors:
        print(f"ЯКІР-ПОПЕРЕДЖЕННЯ: {error}")
    print(
        f"Markdown-якорі: {count} документів; "
        f"{len(errors)} попереджень; "
        f"режим {'суворий' if args.strict else 'спостережний'}"
    )
    return int(bool(args.strict and errors))


if __name__ == "__main__":
    raise SystemExit(main())
