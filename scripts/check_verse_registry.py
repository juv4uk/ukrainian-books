#!/usr/bin/env python3
"""Звірити власний індекс віршів і за потреби локальні свідки SARIT/GRETIL.

Жодного мережевого запиту або копіювання стороннього корпусу в репозиторій.
Структурна перевірка JSON без зовнішніх джерел не доводить точності перекладу.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "research" / "ashtavakra" / "verse-registry.json"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
PRINTED = re.compile(r"\|\|(\d+)\|(\d+)\|{2,}")
GRETIL = re.compile(r"Avg_(\d+)\.(\d+)")
SARIT_ID = re.compile(r"verse_(\d+)\.(\d+)")


def analyze_sarit(root: ET.Element) -> tuple[list[str], list[str]]:
    xml_ids: list[str] = []
    printed: list[str] = []
    for elem in root.iter():
        match = SARIT_ID.fullmatch(elem.get(XML_ID, ""))
        if match:
            xml_ids.append(f"{int(match[1])}.{int(match[2])}")
        if elem.tag.rsplit("}", 1)[-1] == "l":
            for m in PRINTED.finditer("".join(elem.itertext())):
                printed.append(f"{int(m[1])}.{int(m[2])}")
    return xml_ids, printed


def check_ids(found: list[str], expected: set[str], label: str, errors: list[str]) -> None:
    counts = Counter(found)
    extra = sorted(set(found) - expected)
    missing = sorted(expected - set(found), key=lambda s: tuple(map(int, s.split("."))))
    duplicates = sorted(k for k, n in counts.items() if n > 1)
    print(f"{label}: {len(found)} позначок, {len(counts)} різних")
    if extra or missing or duplicates:
        errors.append(
            f"{label}: зайві={extra[:10]}, відсутні={missing[:10]}, дублікати={duplicates[:10]}"
        )


def validate_registry(data: dict, errors: list[str]) -> set[str]:
    if data.get("schema_version") != 1:
        errors.append("Невідома версія схеми")
    if data.get("chapter_count") != 20 or data.get("verse_count") != 298:
        errors.append("Очікується 20 глав і 298 номерів")
    chapters = data.get("chapters", [])
    verse_records = data.get("verses", [])
    if len(chapters) != 20:
        errors.append(f"Не 20 глав: {len(chapters)}")
    expected: set[str] = set()
    for index, chapter in enumerate(chapters, start=1):
        n = chapter.get("verse_count", 0)
        if chapter.get("chapter") != index or not isinstance(n, int) or n < 1:
            errors.append(f"Помилка параметрів глави {index}")
            continue
        if chapter.get("first_id") != f"{index}.1" or chapter.get("last_id") != f"{index}.{n}":
            errors.append(f"Неузгоджені межі глави {index}")
        expected.update(f"{index}.{v}" for v in range(1, n + 1))
    ids = [v.get("id") for v in verse_records]
    if len(expected) != 298:
        errors.append(f"Неправильна сума віршів у главах: {len(expected)}")
    if len(verse_records) != 298 or len(set(ids)) != len(ids) or set(ids) != expected:
        errors.append("Віршові картки не відповідають повному індексу 1..298")
    for verse in verse_records:
        ident = verse.get("id")
        if ident not in expected:
            continue
        xml_id = verse.get("sarit_xml_id")
        correct = None if ident == "18.95" else f"verse_{ident}"
        if xml_id != correct or verse.get("sarit_printed_number") is not True:
            errors.append(f"Хибна прив'язка SARIT до {ident}")
        if not verse.get("status"):
            errors.append(f"Невказаний редакційний статус {ident}")
    anomalies = data.get("markup_anomalies", [])
    if not any(a.get("verse") == "18.95" and a.get("kind") == "missing_xml_id" for a in anomalies):
        errors.append("Не задокументовано відсутню XML-мітку SARIT 18.95")
    return expected


def self_test() -> None:
    """Тільки синтетичний фрагмент, не копія стороннього корпусу."""
    sample = (
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body><div n="18">'
        '<lg xml:id="verse_18.96"><l>перший||18|95|||</l>'
        '<l>другий||18|96||</l></lg></div></body></text></TEI>'
    )
    xml_ids, printed = analyze_sarit(ET.fromstring(sample))
    assert xml_ids == ["18.96"], xml_ids
    assert printed == ["18.95", "18.96"], printed
    errors: list[str] = []
    check_ids(printed, {"18.95", "18.96"}, "Тест надрукованих номерів", errors)
    check_ids(xml_ids, {"18.96"}, "Тест XML", errors)
    assert not errors, errors
    print("Самоперевірка синтетичної аномалії SARIT: OK")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sarit", type=Path, help="Локальний XML SARIT (не додавати до Git)")
    parser.add_argument("--gretil", type=Path, help="Локальний текст GRETIL (не додавати до Git)")
    parser.add_argument("--self-test", action="store_true", help="Перевірити розпізнавання 18.95")
    args = parser.parse_args()
    errors: list[str] = []
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    expected = validate_registry(data, errors)
    print(f"Власний реєстр: {len(data['chapters'])} глав, {len(expected)} позицій")

    if args.self_test:
        self_test()
    if args.sarit:
        xml_ids, printed = analyze_sarit(ET.parse(args.sarit).getroot())
        check_ids(printed, expected, "SARIT: номери в тексті", errors)
        # У файлі SARIT відсутня ТІЛЬКИ XML-мітка 18.95, обидва вірші присутні.
        check_ids(xml_ids, expected - {"18.95"}, "SARIT: xml:id з відомою винятковою міткою", errors)
        if "18.95" in xml_ids:
            errors.append("Статус SARIT 18.95 змінився: перегляньте реєстр")
    else:
        print("Зовнішній SARIT XML не подано: фактичний корпус тут не перевірявся")
    if args.gretil:
        raw = args.gretil.read_text(encoding="utf-8")
        ids = [f"{int(m[1])}.{int(m[2])}" for m in GRETIL.finditer(raw)]
        check_ids(ids, expected, "GRETIL: нумерація Avg_", errors)
    else:
        print("Зовнішній GRETIL не подано: повна автоматична звірка не виконувалась")

    for err in errors:
        print("ПОМИЛКА: " + err, file=sys.stderr)
    if errors:
        return 1
    print("OK: внутрішня структура індексу й доступні перевірки")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
