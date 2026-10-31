#!/usr/bin/env python3
"""Перевірка двох редакцій «Аштавакра-ґіти» без копіювання цифрових джерел."""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
ACADEMIC = Path("editorial/academic-edition")
POETIC = Path("editorial/poetic-edition")
REGISTRY = Path("research/ashtavakra/registry-20-chapters.csv")
NAME = re.compile(r"^(?:[1-9]|1\d|20)\.[1-9]\d*\.json$")
CYR = re.compile(r"[\u0400-\u052f]")
DEVA = re.compile(r"[\u0900-\u097f]")
STATUSES = {"чернетка", "перевірено", "рецензовано"}


def text(value):
    return isinstance(value, str) and bool(value.strip())


def https(value):
    if not text(value):
        return False
    u = urlparse(value)
    return u.scheme == "https" and bool(u.netloc) and not u.username and not u.password


def fields(errors, item, allowed, where):
    if not isinstance(item, dict):
        errors.append(f"{where}: очікується об'єкт")
        return {}
    for key in allowed:
        if key not in item:
            errors.append(f"{where}: бракує поля {key}")
    for key in sorted(set(item) - set(allowed)):
        errors.append(f"{where}: невідоме поле {key}")
    return item


def expected_verses(root):
    path = root / REGISTRY
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    chapters = set()
    ids = set()
    for row in rows:
        ch = row["глава"]
        if ch == "разом":
            continue
        if not ch.isdigit() or not 1 <= int(ch) <= 20 or ch in chapters:
            raise ValueError("Повторена або недійсна глава")
        chapters.add(ch)
        count = int(row["GRETIL_віршів"])
        if count < 1:
            raise ValueError("Глава без віршів")
        ids.update(f"{ch}.{i}" for i in range(1, count + 1))
    if chapters != {str(i) for i in range(1, 21)} or len(ids) != 298:
        raise ValueError("Очікуються 20 глав і 298 позицій")
    return ids


def common(v, label, release, errors):
    if v.get("status") not in STATUSES:
        errors.append(f"{label}: недійсний редакторський статус")
    rights = fields(errors, v.get("rights"),
                    ("verified", "evidence_url", "owned_ukrainian_text", "devanagari_permitted"),
                    label + "/права")
    review = fields(errors, v.get("review"), ("reviewer", "evidence_url"), label + "/рецензія")
    for flag in ("verified", "owned_ukrainian_text", "devanagari_permitted"):
        if type(rights.get(flag)) is not bool:
            errors.append(f"{label}: rights.{flag} мусить бути bool")
    if rights.get("evidence_url") is not None and not https(rights["evidence_url"]):
        errors.append(f"{label}: URL доказу прав недійсний")
    if review.get("evidence_url") is not None and not https(review["evidence_url"]):
        errors.append(f"{label}: URL рецензії недійсний")
    if review.get("reviewer") is not None and not text(review["reviewer"]):
        errors.append(f"{label}: ім'я рецензента порожнє")
    if release:
        if v.get("status") != "рецензовано" or not text(review.get("reviewer")) or not https(review.get("evidence_url")):
            errors.append(f"{label}: бракує доказу незалежного рецензування")
        if rights.get("verified") is not True or rights.get("owned_ukrainian_text") is not True or not https(rights.get("evidence_url")):
            errors.append(f"{label}: права на український текст не підтверджено")
    return rights


def academic(v, release):
    errors = []
    v = fields(errors, v,
               ("id", "status", "source", "lines", "research_notes",
                "ukrainian_parallels", "illustration", "rights", "review"), "академічна картка")
    label = f"академічна/{v.get('id', '?')}"
    rights = common(v, label, release, errors)
    source = fields(errors, v.get("source"),
                    ("witness", "url", "locator", "edition_note", "license_note"), label + "/джерело")
    for key in ("witness", "locator", "edition_note", "license_note"):
        if not text(source.get(key)):
            errors.append(f"{label}: бракує джерельного поля {key}")
    if not https(source.get("url")):
        errors.append(f"{label}: джерело має бути HTTPS")
    lines = v.get("lines")
    if not isinstance(lines, list) or not 2 <= len(lines) <= 4:
        errors.append(f"{label}: потрібно 2–4 рядки")
        lines = []
    for idx, item in enumerate(lines, 1):
        where = f"{label}/рядок {idx}"
        line = fields(errors, item,
                      ("devanagari", "transliteration_uk", "translation_uk", "commentary_uk",
                       "source_locator", "commentary_sources"), where)
        for key, pattern in (("devanagari", DEVA), ("transliteration_uk", CYR),
                             ("translation_uk", CYR), ("commentary_uk", CYR)):
            value = line.get(key)
            if not text(value) or not pattern.search(value):
                errors.append(f"{where}: неправильне поле {key}")
        if not text(line.get("source_locator")):
            errors.append(f"{where}: потрібен точний локатор")
        urls = line.get("commentary_sources")
        if not isinstance(urls, list) or not urls or not all(https(u) for u in urls):
            errors.append(f"{where}: потрібне HTTPS-джерело коментаря")
    notes = v.get("research_notes")
    if not isinstance(notes, list) or not all(text(x) for x in notes):
        errors.append(f"{label}: неправильні дослідницькі примітки")
    parallels = v.get("ukrainian_parallels")
    if not isinstance(parallels, list):
        errors.append(f"{label}: потрібен список українських паралелей")
    else:
        for idx, item in enumerate(parallels, 1):
            where = f"{label}/паралель {idx}"
            p = fields(errors, item, ("figure", "work", "evidence_url", "analogy", "limits"), where)
            if not all(text(p.get(x)) for x in ("figure", "work", "analogy", "limits")) or not https(p.get("evidence_url")):
                errors.append(f"{where}: потрібні доказ, зміст і межі культурної паралелі")
    if v.get("illustration") is not None:
        il = fields(errors, v["illustration"],
                    ("brief", "alt_uk", "rights_verified", "rights_evidence_url"), label + "/ілюстрація")
        if not text(il.get("brief")) or not text(il.get("alt_uk")) or not CYR.search(il.get("alt_uk", "")):
            errors.append(f"{label}: ілюстрації бракує завдання/українського опису")
        if type(il.get("rights_verified")) is not bool:
            errors.append(f"{label}: некоректний прапорець прав ілюстрації")
        if il.get("rights_evidence_url") is not None and not https(il["rights_evidence_url"]):
            errors.append(f"{label}: неправильна URL-адреса прав ілюстрації")
        if release and (il.get("rights_verified") is not True or not https(il.get("rights_evidence_url"))):
            errors.append(f"{label}: права ілюстрації не підтверджені")
    if release and rights.get("devanagari_permitted") is not True:
        errors.append(f"{label}: право відтворювати деванагарі не підтверджено")
    return errors


def poetic(v, release):
    errors = []
    v = fields(errors, v,
               ("id", "status", "author", "stanzas_uk", "meaning_review", "rights", "review"),
               "поетична картка")
    label = f"поетична/{v.get('id', '?')}"
    common(v, label, release, errors)
    if not text(v.get("author")):
        errors.append(f"{label}: потрібен автор")
    lines = v.get("stanzas_uk")
    if not isinstance(lines, list) or not lines or not all(text(x) and CYR.search(x) for x in lines):
        errors.append(f"{label}: потрібні українські поетичні рядки")
    meaning = fields(errors, v.get("meaning_review"),
                     ("scholarly_id", "editorial_note"), label + "/зміст")
    if meaning.get("scholarly_id") != v.get("id") or not text(meaning.get("editorial_note")):
        errors.append(f"{label}: потрібне зіставлення з академічним віршем")
    return errors


def load(root, subdir, expected, validate, release):
    found, errors = {}, []
    folder = root / subdir
    if not folder.is_dir():
        return found, errors
    for path in sorted(folder.glob("*.json")):
        if path.is_symlink() or not NAME.fullmatch(path.name):
            errors.append(f"{subdir}/{path.name}: недопустимий шлях")
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError, OSError) as exc:
            errors.append(f"{path}: помилка JSON/UTF-8 ({type(exc).__name__})")
            continue
        if not isinstance(data, dict) or data.get("id") != path.stem or path.stem not in expected:
            errors.append(f"{path}: ID не відповідає реєстру")
            continue
        errors.extend(validate(data, release))
        found[path.stem] = data
    return found, errors


def audit(root, release=False):
    try:
        expected = expected_verses(root)
    except (ValueError, OSError, KeyError) as exc:
        return {}, {}, {"академічних": 0, "поетичних": 0, "очікується": 298, "помилки": [str(exc)]}
    a, ea = load(root, ACADEMIC, expected, academic, release)
    p, ep = load(root, POETIC, expected, poetic, release)
    errors = ea + ep
    if release:
        for title, records in (("Академічний том", a), ("Поетичний том", p)):
            missing = sorted(expected - set(records), key=lambda z: tuple(map(int, z.split("."))))
            if missing:
                errors.append(f"{title}: бракує {len(missing)} віршів; перший {missing[0]}")
    return a, p, {"академічних": len(a), "поетичних": len(p),
                  "очікується": len(expected), "помилки": errors, "режим_релізу": release}


def preview(academic_records, poetic_records, out):
    """Два окремі markdown-рукописи; деванагарі не розкривається без прав."""
    out.mkdir(parents=True, exist_ok=True)
    warning = "# ЧЕРНЕТКА — НЕ ДЛЯ ВИДАННЯ\n\nНе засвідчує рецензування чи права на PDF/EPUB.\n"
    scholarly = [warning, "\n## Построкове академічне читання\n"]
    poems = [warning, "\n## Окремий український поетичний переклад\n"]
    order = lambda i: tuple(map(int, i.split(".")))
    for vid in sorted(academic_records, key=order):
        card = academic_records[vid]
        scholarly.append(f"\n### {vid} — {card['status']}\n")
        for n, line in enumerate(card["lines"], 1):
            permitted = card["rights"]["verified"] and card["rights"]["devanagari_permitted"]
            deva = line["devanagari"] if permitted else "[Приховано: прав на деванагарі не підтверджено]"
            scholarly.extend([
                f"\n**Рядок {n}, деванагарі:** {deva}\n",
                f"\n**Українська транслітерація:** {line['transliteration_uk']}\n",
                f"\n**Український переклад:** {line['translation_uk']}\n",
                f"\n**Науковий коментар:** {line['commentary_uk']}\n",
                f"\nДжерело: {card['source']['url']} — {line['source_locator']}\n",
            ])
        for par in card["ukrainian_parallels"]:
            scholarly.append(f"\n**Українська паралель:** {par['figure']} — {par['work']}; {par['analogy']}. **Межі:** {par['limits']}. Джерело: {par['evidence_url']}\n")
        if card["illustration"]:
            il = card["illustration"]
            scholarly.append(f"\n**Незатверджена ілюстрація:** {il['brief']}; опис: {il['alt_uk']}\n")
    for vid in sorted(poetic_records, key=order):
        card = poetic_records[vid]
        poems.append(f"\n### {vid} — {card['status']}\n\n" + "\n".join(card["stanzas_uk"]) + "\n")
    (out / "akademichna-chernetka.md").write_text("".join(scholarly), encoding="utf-8")
    (out / "poetychna-chernetka.md").write_text("".join(poems), encoding="utf-8")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--release", action="store_true")
    p.add_argument("--preview-out", type=Path)
    args = p.parse_args(argv)
    if args.release and args.preview_out:
        p.error("--release і чернетковий перегляд несумісні")
    a, b, report = audit(args.root, args.release)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["помилки"]:
        return 1
    if args.preview_out:
        preview(a, b, args.preview_out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
