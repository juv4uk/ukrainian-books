#!/usr/bin/env python3
"""Незалежно перевірити нумерацію та дві особливості розмітки SARIT.

Основу становить уже злитий реєстр (PR #12), без створення другого реєстру.
За замовчуванням перевіряємо лише локальну CSV і синтетичний тест:
повної звірки з чужими цифровими корпусами без --sarit/--gretil НЕ було.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "research/ashtavakra/registry-20-chapters.csv"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
ID_PATTERN = re.compile(r"verse_(\d+)\.(\d+)")
PRINTED = re.compile(r"\|\|(\d+)\|(\d+)\|{2,}")
GRETIL = re.compile(r"Avg_(\d+)\.(\d+)")


def expected_from_csv(errors: list[str]) -> set[str]:
    with INDEX.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    chapters = [row for row in rows if row.get("глава") != "разом"]
    if len(chapters) != 20:
        errors.append(f"Очікувалося 20 глав, отримано {len(chapters)}")
    expected: set[str] = set()
    total_gretil = total_sarit_lg = 0
    for n, row in enumerate(chapters, 1):
        if row["глава"] != str(n):
            errors.append(f"Глава {n} пропущена чи не за порядком")
            continue
        try:
            gretil_count = int(row["GRETIL_віршів"])
            sarit_lg_count = int(row["SARIT_віршів"])
        except (KeyError, ValueError):
            errors.append(f"Хибні числові поля для глави {n}")
            continue
        if gretil_count <= 0:
            errors.append(f"Неприпустима кількість у главі {n}")
            continue
        # CSV PR #12 підраховує ТІЛЬКИ позначені <lg>, не всі xml:id і не друковані номери.
        expected_lg = gretil_count - (1 if n in (1, 18) else 0)
        if sarit_lg_count != expected_lg:
            errors.append(f"Неочікувана кількість SARIT <lg> у главі {n}: {sarit_lg_count}")
        total_gretil += gretil_count
        total_sarit_lg += sarit_lg_count
        expected.update(f"{n}.{verse}" for verse in range(1, gretil_count + 1))
    if len(expected) != 298 or total_gretil != 298 or total_sarit_lg != 296:
        errors.append("Очікувана структура: 20 глав, 298 номерів, 296 позначених <lg>")
    totals = [r for r in rows if r.get("глава") == "разом"]
    if len(totals) != 1 or totals[0].get("GRETIL_віршів") != "298" or totals[0].get("SARIT_віршів") != "296":
        errors.append("Підсумковий рядок CSV некоректний")
    return expected


def inspect_sarit_xml(root: ET.Element) -> tuple[list[str], list[str], list[str]]:
    """XML-ID на всіх елементах, надруковані номери й лише ID на <lg>."""
    xml_ids: list[str] = []
    printed: list[str] = []
    lg_ids: list[str] = []
    for element in root.iter():
        match = ID_PATTERN.fullmatch(element.attrib.get(XML_ID, ""))
        kind = element.tag.rsplit("}", 1)[-1]
        if match:
            verse_id = f"{int(match[1])}.{int(match[2])}"
            xml_ids.append(verse_id)
            if kind == "lg":
                lg_ids.append(verse_id)
        if kind == "l":
            for m in PRINTED.finditer("".join(element.itertext())):
                printed.append(f"{int(m[1])}.{int(m[2])}")
    return xml_ids, printed, lg_ids


def compare(found: list[str], expected: set[str], label: str, errors: list[str]) -> None:
    duplicates = sorted(k for k, n in Counter(found).items() if n > 1)
    missing = sorted(expected - set(found), key=lambda x: tuple(map(int, x.split("."))))
    extra = sorted(set(found) - expected)
    print(f"{label}: {len(found)} номерів ({len(set(found))} унікальних)")
    if duplicates or missing or extra:
        errors.append(f"{label}: дублікати={duplicates[:6]}, пропуски={missing[:6]}, зайві={extra[:6]}")


def self_test() -> None:
    """Синтетичні дані: нічого не скопійовано з цифрового санскритського корпусу."""
    sample = (
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>'
        '<div n="1"><lg><l xml:id="verse_1.1">тест||1|1||</l></lg></div>'
        '<div n="18"><lg xml:id="verse_18.96">'
        '<l>перший||18|95|||</l><l>другий||18|96||</l>'
        '</lg></div></body></text></TEI>'
    )
    xml_ids, printed, lg_ids = inspect_sarit_xml(ET.fromstring(sample))
    assert xml_ids == ["1.1", "18.96"], xml_ids
    assert printed == ["1.1", "18.95", "18.96"], printed
    assert lg_ids == ["18.96"], lg_ids
    print("OK: синтетичні кейси 1.1 (<l>) та 18.95/18.96 (спільний <lg>)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sarit", type=Path, help="Шлях до локального SARIT XML (не додавати у Git)")
    parser.add_argument("--gretil", type=Path, help="Шлях до локального GRETIL HTML/TXT (не додавати у Git)")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    errors: list[str] = []
    expected = expected_from_csv(errors)
    print(f"Реєстр PR #12: {len(expected)} очікуваних номерів")
    if args.self_test:
        self_test()
    if args.sarit:
        xml_ids, printed, lg_ids = inspect_sarit_xml(ET.parse(args.sarit).getroot())
        compare(printed, expected, "SARIT: надруковані маркери", errors)
        compare(xml_ids, expected - {"18.95"}, "SARIT: усі xml:id", errors)
        compare(lg_ids, expected - {"1.1", "18.95"}, "SARIT: лише <lg xml:id>", errors)
    else:
        print("SARIT не подано: зовнішню перевірку не виконано")
    if args.gretil:
        raw = args.gretil.read_text(encoding="utf-8")
        ids = [f"{int(m[1])}.{int(m[2])}" for m in GRETIL.finditer(raw)]
        compare(ids, expected, "GRETIL: Avg_", errors)
    else:
        print("GRETIL не подано: зовнішню перевірку не виконано")
    for e in errors:
        print("ПОМИЛКА: " + e, file=sys.stderr)
    if errors:
        return 1
    print("OK: індекс, повнота та доступні перевірки")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
