#!/usr/bin/env python3
"""Контроль українських паралелей: жодної вигаданої цитати.

Це найризикованіше місце всієї книги. Спокуса написати «як казав Шевченко…»
з пам'яті велика, а перевірити таку цитату читач не може. Тому тут діє
жорстке правило: **паралель або не цитує взагалі, або цитує з адресою**.

Три дозволені види запису (`kind`):

``наша паралель``
    Вказівка на твір **без цитати**. Текст мусить містити слово «наша»
    (паралель / інтерпретація / асоціація) — тобто прямо казати, що це наша
    думка, а не твердження про вплив. Лапки-цитати в такому записі заборонені.

``цитата``
    Дослівна цитата. Обов'язкові: `quote`, `quote_url` (HTTPS із білого
    списку бібліотек), `quote_section`, `quote_edition` (друковане джерело)
    і `quote_checked_on`. Цитата мусить **дослівно** стояти в полі `text` —
    інакше запис суперечить сам собі.

``ПОТРЕБУЄ ПЕРЕВІРКИ``
    Паралель непевна. Жодних цитат; текст мусить містити цю позначку.

Що це НЕ перевіряє: чи справді наведений URL містить цю цитату (для цього
потрібна мережа й людське око), і чи справді твір належить названому авторові.
Перевірка гарантує **форму**: адреса є, розділ названий, цитата не вигадана
«на око» всередині самого реєстру.

Вжиток:
    python3 scripts/check_ukrainian_parallels.py
    python3 scripts/check_ukrainian_parallels.py --json
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "books" / "ashtavakra-gita" / "paraleli.json"
INDEX = ROOT / "research" / "ashtavakra" / "registry-20-chapters.csv"

KINDS = ("наша паралель", "цитата", "ПОТРЕБУЄ ПЕРЕВІРКИ")
FIELDS = (
    "id", "verse", "kind", "figure", "work", "text",
    "quote", "quote_url", "quote_section", "quote_edition", "quote_checked_on",
)
ID_RE = re.compile(r"^([1-9]\d*)-([1-9]\d*)$")

# Білий список: українські бібліотеки першоджерел і канонічних текстів.
# Поза ним цитата не приймається навіть із HTTPS — інакше «перевірено»
# означало б «знайшлося в інтернеті».
ALLOWED_HOSTS = frozenset({
    "izbornyk.org.ua", "www.izbornyk.org.ua",
    "litopys.org.ua", "www.litopys.org.ua",
    "ukrlib.com.ua", "www.ukrlib.com.ua",
    "myslenedrevo.com.ua", "www.myslenedrevo.com.ua",
    "diasporiana.org.ua", "www.diasporiana.org.ua",
})

# Лапки-цитата. Назви творів теж беруться в «», тому лапки самі по собі
# ще не цитата: цитатою вважається лише те, чого немає серед назв.
TITLE_QUOTES = re.compile(r"«([^»]{1,200})»")
# Маркери «це наша думка» — обов'язкові в записі виду «наша паралель».
OUR_MARKERS = ("наша паралель", "наша інтерпретація", "наша асоціація",
               "наше порівняння", "наша думка")
UNVERIFIED = "ПОТРЕБУЄ ПЕРЕВІРКИ"


def filled(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def valid_date(value: object) -> bool:
    if not filled(value):
        return False
    try:
        return date.fromisoformat(str(value)).isoformat() == value
    except ValueError:
        return False


def valid_url(value: object) -> bool:
    if not filled(value):
        return False
    try:
        parsed = urlparse(str(value))
    except ValueError:
        return False
    return (parsed.scheme == "https" and bool(parsed.hostname)
            and not parsed.username and not parsed.password
            and parsed.hostname in ALLOWED_HOSTS)


def verse_ids(csv_path: Path = INDEX) -> set[str]:
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = [r for r in csv.DictReader(handle) if r.get("глава") != "разом"]
    ids: set[str] = set()
    for chapter, row in enumerate(rows, 1):
        for verse in range(1, int(row["GRETIL_віршів"]) + 1):
            ids.add(f"{chapter}.{verse}")
    return ids


def own_texts(verse: str, cards: Path | None = None) -> list[str]:
    """Наш власний текст вірша: переклад і дослівне значення з картки.

    Лапки навколо **нашого** перекладу — не цитата чужого автора. Щоб
    перевірка не била по них, дозволяємо будь-який уривок, що справді
    стоїть у картці цього вірша.
    """
    base = cards or (ROOT / "editorial" / "cards")
    path = base / f"{verse}.json"
    if not path.is_file():
        return []
    try:
        card = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [str(card.get(name) or "").casefold()
            for name in ("ukrainian_translation", "literal_meaning")]


def validate(record: object, known: set[str], ours: list[str] | None = None,
             registered: tuple[str, ...] = ()) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["запис має бути JSON-об'єктом"]
    for field in FIELDS:
        if field not in record:
            errors.append(f"відсутнє поле {field!r}")
    extra = sorted(set(record) - set(FIELDS))
    if extra:
        errors.append(f"невідомі поля {extra}")

    ident = record.get("id")
    if not isinstance(ident, str) or not ID_RE.fullmatch(ident):
        errors.append(f"неприпустимий id {ident!r} (очікується «глава-вірш»)")
    verse = record.get("verse")
    if not isinstance(verse, str) or verse not in known:
        errors.append(f"вірш {verse!r} відсутній у реєстрі 20 глав")

    kind = record.get("kind")
    if kind not in KINDS:
        errors.append(f"невідомий вид паралелі {kind!r}; дозволено {KINDS}")
        return errors

    for field in ("figure", "work", "text"):
        if not filled(record.get(field)):
            errors.append(f"{field}: мусить бути непорожнім текстом")
    text = record.get("text") if isinstance(record.get("text"), str) else ""

    titles = [record.get("work") or "", record.get("figure") or ""]
    allowed = " ".join(ours or []).casefold()
    quoted = []
    for span in TITLE_QUOTES.findall(text):
        bare = span.strip()
        if any(bare in title for title in titles):
            continue                       # назва твору
        if bare.casefold() in allowed:
            continue                       # наш власний переклад цього вірша
        if bare in registered:
            continue                       # зареєстрована цитата
        quoted.append(bare)
    has_quote_fields = any(record.get(name) is not None for name in
                           ("quote", "quote_url", "quote_section",
                            "quote_edition", "quote_checked_on"))

    if kind == "наша паралель":
        if quoted:
            errors.append("«наша паралель» цитує чужі слова в лапках, але не має "
                          "адреси: або переносьте запис у вид «цитата» з URL, "
                          "розділом і друкованим джерелом, або приберіть лапки "
                          f"({quoted[:2]})")
        if has_quote_fields:
            errors.append("«наша паралель» не може мати полів quote_*")
        folded = text.casefold()
        if not any(marker in folded for marker in OUR_MARKERS):
            errors.append("«наша паралель» мусить прямо казати, що це наша "
                          "інтерпретація (напр. «Наша паралель: …»)")

    elif kind == UNVERIFIED:
        if UNVERIFIED not in text:
            errors.append(f"вид «{UNVERIFIED}» вимагає цієї позначки в тексті")
        if quoted or has_quote_fields:
            errors.append(f"«{UNVERIFIED}» не може містити цитат ({quoted[:2]})")
        if record.get("quote") is not None:
            errors.append("неперевірена паралель не може мати поля quote")

    else:  # цитата
        for name in ("quote", "quote_url", "quote_section", "quote_edition"):
            if not filled(record.get(name)):
                errors.append(f"цитата без {name}: адреса обов'язкова")
        if not valid_date(record.get("quote_checked_on")):
            errors.append("цитата без дати перевірки (quote_checked_on, YYYY-MM-DD)")
        if not valid_url(record.get("quote_url")):
            errors.append("quote_url має бути HTTPS із білого списку бібліотек: "
                          + ", ".join(sorted(ALLOWED_HOSTS)))
        quote = record.get("quote")
        if filled(quote) and quote not in text:
            errors.append("цитата не стоїть дослівно в полі text: "
                          "запис суперечить сам собі")
    return errors


def audit(path: Path = REGISTER, index: Path = INDEX) -> dict:
    errors: list[str] = []
    if not path.is_file():
        return {"status": "failed", "errors": [f"немає реєстру {path}"],
                "parallels": 0, "by_kind": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "failed", "errors": [str(exc)], "parallels": 0,
                "by_kind": {}}
    if data.get("schema_version") != 1:
        errors.append("schema_version має бути 1")
    extra = sorted(set(data) - {"schema_version", "note", "parallels"})
    if extra:
        errors.append(f"невідомі поля реєстру: {extra}")
    records = data.get("parallels")
    if not isinstance(records, list):
        return {"status": "failed", "errors": errors + ["parallels має бути списком"],
                "parallels": 0, "by_kind": {}}

    known = verse_ids(index)
    seen_ids: set[str] = set()
    by_verse: dict[str, list[str]] = {}
    by_kind: dict[str, int] = {}
    for position, record in enumerate(records):
        ident = record.get("id") if isinstance(record, dict) else None
        if isinstance(ident, str):
            if ident in seen_ids:
                errors.append(f"повторений id паралелі: {ident}")
            seen_ids.add(ident)
        if isinstance(record, dict) and isinstance(record.get("verse"), str):
            by_verse.setdefault(record["verse"], []).append(str(ident))
        if isinstance(record, dict) and record.get("kind") in KINDS:
            by_kind[record["kind"]] = by_kind.get(record["kind"], 0) + 1
        for message in validate(record, known,
                                ours=own_texts(str(record.get("verse") or ""))
                                if isinstance(record, dict) else [],
                                registered=tuple(
                                    str(r.get("quote")) for r in records
                                    if isinstance(r, dict) and r.get("quote"))):
            errors.append(f"паралель #{position} ({ident}): {message}")

    for verse, idents in sorted(by_verse.items()):
        if len(idents) > 1:
            errors.append(f"вірш {verse} має {len(idents)} паралелей: {idents}")

    return {
        "status": "ok" if not errors else "failed",
        "parallels": len(records),
        "by_kind": by_kind,
        "quotes": sum(1 for r in records
                      if isinstance(r, dict) and r.get("kind") == "цитата"),
        "verses_covered": len(by_verse),
        "errors": errors,
        "scope": ("форма записів, не істинність цитат: чи справді URL містить "
                  "цитату — перевіряє людина"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = audit()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Паралелей: {result['parallels']}; віршів покрито: "
              f"{result['verses_covered']}; за видами: {result['by_kind']}")
        for error in result["errors"]:
            print("ПОМИЛКА: " + error, file=sys.stderr)
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
