#!/usr/bin/env python3
"""Незмінювальний аудит построкового вирівнювання наукових глав.

Пошаровість ЦІЛОГО вірша не дорівнює построковості його піввіршів.
Цей інструмент перевіряє лише наявність та структуру відображених шарів.
Він не перевіряє переклад, джерелознавство, права чи незалежну рецензію.

Вжиток:
  python3 scripts/audit_postrokovosti.py
  python3 scripts/audit_postrokovosti.py --all
  python3 scripts/audit_postrokovosti.py --strict --all
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT / "books" / "ashtavakra-gita"
LABELS = ("Деванагарі", "IAST", "Українська транслітерація", "Переклад")
COMMENTS = ("Коментар", "Науковий коментар")
VERSE = re.compile(r"^##\s+(\d+\.\d+)\s*$", re.M)
LINE = re.compile(r"^###\s+Рядок\s+([аб])\s*$", re.M)
FIELD = re.compile(r"^\*\*([^*]+?)\.\*\*\s*(\S.*?)\s*$", re.M)


def fields(block: str) -> dict[str, str]:
    """Прочитати тільки явно підписані непорожні шари Markdown."""
    return {name: content.strip() for name, content in FIELD.findall(block)}


def count_source_lines(data: dict[str, str]) -> int | None:
    """Кількість надрукованих санскритських піврядків, не перекладів."""
    if data.get("IAST"):
        chunks = [chunk.strip() for chunk in re.split(r"\|+", data["IAST"]) if chunk.strip()]
        return len(chunks) or None
    if data.get("Деванагарі"):
        chunks = [chunk.strip() for chunk in re.split(r"[।॥]+", data["Деванагарі"]) if chunk.strip()]
        return len(chunks) or None
    return None


def verse_report(identifier: str, body: str) -> dict:
    """Повернути вердикт про *верстку*, а не наукову якість вірша."""
    headings = list(LINE.finditer(body))
    global_block = body[:headings[0].start()] if headings else body
    global_fields = fields(global_block)
    segments: list[dict] = []
    for index, match in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(body)
        segment = fields(body[match.end():end])
        segments.append({"рядок": match.group(1), "пропущено": [key for key in LABELS if key not in segment]})

    # Складені окремі рядки не повинні здаватися одним віршем через те,
    # що dict залишає лише останнє однойменне поле.
    all_data = fields(body)
    sources = dict(all_data)
    if headings:
        for name in ("IAST", "Деванагарі"):
            fragments = [fields(body[mark.end():headings[i + 1].start()
                                     if i + 1 < len(headings) else len(body)]).get(name)
                         for i, mark in enumerate(headings)]
            if all(fragments):
                sources[name] = " ".join(fragments)
    expected = count_source_lines(sources)
    missing_comment = not any(marker in all_data for marker in COMMENTS)
    missing_verse = [name for name in ("Деванагарі", "Українська транслітерація", "Переклад")
                     if name not in all_data]
    labels_order = [part["рядок"] for part in segments]
    correct_order = labels_order == ["а", "б"] if expected == 2 else False
    repeated_at_verse_level = any(name in global_fields for name in LABELS)
    if not headings and not missing_verse and not missing_comment:
        status = "пошарово_за_віршем"
    elif (expected == 2 and correct_order and not missing_comment
          and not repeated_at_verse_level and all(not s["пропущено"] for s in segments)):
        status = "построково_за_формою"
    else:
        status = "неповно_або_неузгоджено"
    return {
        "вірш": identifier,
        "стан": status,
        "очікувано_санскритських_рядків": expected,
        "наявно_позначених_рядків": len(segments),
        "немає_шарів_вірша": missing_verse,
        "немає_коментаря": missing_comment,
        "деталі_рядків": segments,
    }


def audit_text(source: str) -> list[dict]:
    """Збирати саме вірші, не заголовки глав чи поетичну частину."""
    markers = list(VERSE.finditer(source))
    report = []
    for i, marker in enumerate(markers):
        end = markers[i + 1].start() if i + 1 < len(markers) else len(source)
        body = source[marker.end():end].split("\n## Поетичний переклад", 1)[0]
        report.append(verse_report(marker.group(1), body))
    return report


def run(paths: list[Path]) -> dict:
    books = []
    for path in paths:
        if not path.is_file():
            continue
        verses = audit_text(path.read_text(encoding="utf-8"))
        counts = {status: sum(v["стан"] == status for v in verses)
                  for status in ("построково_за_формою", "пошарово_за_віршем", "неповно_або_неузгоджено")}
        books.append({"файл": str(path), "усього_віршів": len(verses), "підсумок": counts,
                      "вірші": verses})
    return {"призначення": "лише контроль структури; не доказ точності, прав чи рецензії",
            "файлів": len(books), "віршів": sum(b["усього_віршів"] for b in books),
            "построково_за_формою": sum(b["підсумок"]["построково_за_формою"] for b in books),
            "книги": books}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="перевірити всі наукові глави")
    parser.add_argument("--chapter", type=int, default=1, help="номер глави (типово 1)")
    parser.add_argument("--strict", action="store_true", help="повернути 1, якщо не всі вірші построкові")
    args = parser.parse_args(argv)
    paths = (sorted(BOOK.glob("rozdil-*-naukove.md")) if args.all else
             [BOOK / f"rozdil-{args.chapter}-naukove.md"])
    report = run(paths)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["файлів"] or not report["віршів"]:
        return 2
    if args.strict and report["построково_за_формою"] != report["віршів"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
