#!/usr/bin/env python3
"""Офлайнове редакторське прев'ю ОКРЕМОГО поетичного тому «Аштавакра-ґіти».

Ні Markdown-прев'ю, ні успішний тест НЕ підтверджують права на публікацію,
достатність санскритологічної звірки, незалежну рецензію чи готовність PDF.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "editorial" / "poetic_samples"
REGISTRY = ROOT / "research" / "ashtavakra" / "registry-20-chapters.csv"
ID = re.compile(r"^([1-9][0-9]*)\.([1-9][0-9]*)$")
STATUSES = {"чернетка", "рецензовано"}
HEADER = (
    "# Аштавакра-ґіта — проба ОКРЕМОГО поетичного перекладу\n\n"
    "> **Редакторське прев'ю. НЕ ДЛЯ ПУБЛІКАЦІЇ.** У цьому файлі немає "
    "оригінального санскритського тексту; кожну строфу треба незалежно звірити "
    "з першоджерелом. Відсутні строфи не домислюємо.\n"
)


def https_url(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed = urlsplit(value)
        return parsed.scheme == "https" and bool(parsed.hostname) and not (
            parsed.username or parsed.password
        )
    except ValueError:
        return False


def expected_ids(csv_path: Path) -> set[str]:
    """Читати ЧИННИЙ реєстр 20 глав, а не вигадувати власну нумерацію."""
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = [r for r in csv.DictReader(handle) if r.get("глава") != "разом"]
    if len(rows) != 20:
        raise ValueError("Реєстр мусить містити 20 глав")
    ids: set[str] = set()
    for chapter, row in enumerate(rows, 1):
        if row["глава"] != str(chapter):
            raise ValueError("Непослідовна глава в реєстрі")
        count = int(row["GRETIL_віршів"])
        if count <= 0:
            raise ValueError("Порожня глава в реєстрі")
        ids.update(f"{chapter}.{verse}" for verse in range(1, count + 1))
    if len(ids) != 298:
        raise ValueError("Невідповідна кількість очікуваних віршів: не 298")
    return ids


def validate(data: object, expected: set[str] | None = None) -> list[str]:
    if not isinstance(data, dict):
        return ["Очікується JSON-об'єкт"]
    errors: list[str] = []
    allowed = {
        "schema_version", "id", "status", "translator", "source",
        "lines", "translation_note", "rights", "review",
    }
    if set(data) != allowed:
        errors.append("Неправильний набір ключів поетичної картки")
    if data.get("schema_version") != 1 or type(data.get("schema_version")) is not int:
        errors.append("schema_version має дорівнювати 1")
    ident = data.get("id")
    if not isinstance(ident, str) or not ID.fullmatch(ident):
        errors.append("Невалідний ID вірша")
    elif expected is not None and ident not in expected:
        errors.append(f"ID {ident} відсутній у реєстрі")
    status = data.get("status")
    if status not in STATUSES:
        errors.append("Неприпустимий статус")
    translator = data.get("translator")
    if translator is not None and (not isinstance(translator, str) or not translator.strip()):
        errors.append("translator має бути непорожнім ім'ям або null")
    source = data.get("source")
    if not isinstance(source, dict) or set(source) != {"gretil", "sarit", "locators"}:
        errors.append("Потрібні два джерела й номери вірша")
    else:
        if not https_url(source.get("gretil")) or not https_url(source.get("sarit")):
            errors.append("Джерела повинні мати HTTPS URL")
        if not isinstance(source.get("locators"), str) or not source["locators"].strip():
            errors.append("Потрібний локатор обох свідків")
    lines = data.get("lines")
    if not isinstance(lines, list) or not 2 <= len(lines) <= 12 or any(
        not isinstance(l, str) or not l.strip() or "\n" in l for l in lines
    ):
        errors.append("Поетична строфа повинна містити 2–12 непорожніх рядків")
    note = data.get("translation_note")
    if note is not None and (not isinstance(note, str) or not note.strip()):
        errors.append("Примітка перекладача має бути рядком або null")
    rights = data.get("rights")
    if not isinstance(rights, dict) or set(rights) != {"own_ukrainian_poem", "verified", "basis"}:
        errors.append("Потрібен окремий паспорт прав на поетичний текст")
        rights = {}
    if type(rights.get("own_ukrainian_poem")) is not bool or type(rights.get("verified")) is not bool:
        errors.append("Поля rights мають бути булевими")
    if not isinstance(rights.get("basis"), str) or not rights["basis"].strip():
        errors.append("Потрібна текстова підстава прав")
    review = data.get("review")
    if not isinstance(review, dict) or set(review) != {"reviewer", "review_url"}:
        errors.append("Неповні поля рецензування")
        review = {}
    for key in ("reviewer", "review_url"):
        val = review.get(key)
        if val is not None and (not isinstance(val, str) or not val.strip()):
            errors.append(f"review.{key} має бути непорожнім або null")
    if status == "рецензовано":
        if not isinstance(translator, str) or not translator.strip():
            errors.append("Рецензованій редакції потрібен автор")
        if rights.get("own_ukrainian_poem") is not True or rights.get("verified") is not True:
            errors.append("Рецензована редакція вимагає позитивних прав")
        if not isinstance(review.get("reviewer"), str) or not review["reviewer"].strip() or not https_url(review.get("review_url")):
            errors.append("Рецензована редакція вимагає окремого рецензента з HTTPS доказом")
        if isinstance(translator, str) and isinstance(review.get("reviewer"), str) and translator.strip().casefold() == review["reviewer"].strip().casefold():
            errors.append("Саморецензування заборонено")
    return errors


def load(root: Path, expected: set[str]) -> tuple[list[dict], list[str]]:
    if root.is_symlink() or not root.is_dir():
        return [], ["Відсутня або символьна тека редакторських поетичних матеріалів"]
    poems: list[dict] = []
    errors: list[str] = []
    seen: set[str] = set()
    for path in sorted(root.glob("*.json")):
        if path.is_symlink():
            errors.append(f"{path.name}: символьні посилання заборонено")
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="strict"))
        except (UnicodeError, OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path.name}: невалідний JSON/UTF-8: {exc}")
            continue
        local_errors = validate(data, expected)
        ident = data.get("id") if isinstance(data, dict) else None
        if isinstance(ident, str):
            if path.name != f"{ident}.json":
                local_errors.append("Ім'я JSON-файлу не збігається з ID")
            if ident in seen:
                local_errors.append("Повторений ID вірша")
            seen.add(ident)
        if local_errors:
            errors.extend(f"{path.name}: {e}" for e in local_errors)
        else:
            poems.append(data)
    if not poems and not errors:
        errors.append("Немає жодного поетичного тексту для прев'ю")
    return poems, errors


def render(poems: list[dict]) -> str:
    result = [HEADER]
    last_chapter = None
    for item in sorted(poems, key=lambda p: tuple(int(v) for v in p["id"].split("."))):
        chapter = item["id"].split(".")[0]
        if chapter != last_chapter:
            result.append(f"\n## Глава {chapter} — поетичні робочі переклади\n")
            last_chapter = chapter
        result.extend([f"\n### {item['id']} — {item['status']}\n", "\n".join(item["lines"]) + "\n"])
        src = item["source"]
        result.append(f"*Звіряння: [GRETIL]({src['gretil']}), [SARIT]({src['sarit']}); {src['locators']}.*\n")
        if item["translation_note"]:
            result.append("*Редакторська примітка:* " + item["translation_note"] + "\n")
    result.append("\n> Це не повний том і не дозвіл на видання. Для окремої поетичної книги потрібні 298 віршів, перевірені права й незалежна рецензія.\n")
    return "\n".join(result)


def check_complete(poems: list[dict], expected: set[str]) -> list[str]:
    ids = {p["id"] for p in poems}
    errors = []
    missing = sorted(expected - ids, key=lambda v: tuple(map(int, v.split("."))))
    if missing:
        errors.append(f"Неповне охоплення: {len(missing)} з 298 віршів відсутні; перший відсутній {missing[0]}")
    for poem in poems:
        if poem["status"] != "рецензовано" or poem["rights"]["verified"] is not True:
            errors.append(f"{poem['id']}: чернетка або непідтверджені права")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=Path, default=SAMPLES)
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    parser.add_argument("--output", type=Path, help="лише редакторське Markdown-прев'ю, НЕ books/")
    parser.add_argument("--check-complete", action="store_true", help="перевірити 298 і незалежний review, без випуску")
    args = parser.parse_args(argv)
    try:
        expected = expected_ids(args.registry)
        poems, errors = load(args.samples, expected)
        if args.check_complete:
            errors += check_complete(poems, expected)
        if errors:
            for err in errors:
                print("ПОМИЛКА: " + err, file=sys.stderr)
            return 1
        output = render(poems)
        if args.output:
            if "books" in args.output.parts:
                print("ПОМИЛКА: прямий запис прев'ю до books/ заборонено", file=sys.stderr)
                return 2
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output, encoding="utf-8")
        else:
            print(output, end="")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ПОМИЛКА джерел: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
