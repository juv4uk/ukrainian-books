#!/usr/bin/env python3
"""Складає власну верстку книги з редакторських карток.

Джерело істини — картки в `editorial/cards`. Скрипт бере лише наші власні
поля (переклад, дослівний сенс, граматику, коментар) і не відтворює чужу
транскрипцію (`sanskrit`, `iast`) — див. `WITNESS_FIELDS`.

Запуск:
    python3 scripts/build_pilot_book.py           # згенерувати
    python3 scripts/build_pilot_book.py --check   # лише перевірити свіжість
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "editorial" / "cards"
GLOSSARY = ROOT / "editorial" / "GLOSSARY.md"
BOOK = ROOT / "books" / "ashtavakra-hita-pilot"

# Глави, де картки покривають кожен вірш реєстру без пропусків.
# Станом на 2026-10-31 це 14 глав із 20: 113 віршів із 298.
# Частково покриті: 1, 15, 18. Без карток: 16, 17, 20.
# Деталі — docs/VYDAVNYCHYI_VYSNOVOK.md.
PILOT_CHAPTERS = (2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 19)

# Поля картки, які є нашим власним внеском і можуть бути зверстані.
OWN_FIELDS = (
    "ukrainian_translation",
    "literal_meaning",
    "grammar",
    "commentary",
)

# Поля, які відтворюють чужу транскрипцію, — у PDF пілота не потрапляють.
WITNESS_FIELDS = ("sanskrit", "iast")

# Терміни, за якими будується покажчик: словник редакції плюс ключові слова
# нашого власного апарату. Покажчик індексує лише ті, що справді трапляються
# в зверстаному тексті, — «мертвих» посилань не буває.
INDEX_TERMS = (
    "ātman", "cit", "sākṣin", "mukti", "vairāgya", "toṣa", "āśrama", "varṇa",
    "jñāna", "ajñāna", "prakṛti", "māyā", "saṃsāra", "bodha", "śānta",
    "nirañjana", "jagat", "viśva", "jīva", "aho", "bahuvrīhi", "katham",
    "yathā", "tathā", "athavā", "namaḥ", "dhīra", "sukha", "duḥkha", "rāga",
    "dveṣa",
)

# Літери з діакритикою → латинська основа: потрібно для сортування в
# makeindex, який не знає IAST і сортував би за байтами.
SORT_MAP = str.maketrans({
    "ā": "a", "ī": "i", "ū": "u", "ṛ": "r", "ṝ": "r", "ḷ": "l", "ḹ": "l",
    "ṃ": "m", "ḥ": "h", "ś": "s", "ṣ": "s", "ṭ": "t", "ḍ": "d", "ñ": "n",
    "ṅ": "n", "ṇ": "n", "Ā": "A", "Ī": "I", "Ū": "U", "Ṛ": "R", "Ṃ": "M",
    "Ḥ": "H", "Ś": "S", "Ṣ": "S", "Ṭ": "T", "Ḍ": "D", "Ñ": "N", "Ṅ": "N",
    "Ṇ": "N",
})

SPECIAL = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


DEVA_RUN = re.compile(r"[\u0900-\u097F]+(?:[ \u0900-\u097F]+)*")


def esc(text: str) -> str:
    """Екранує керівні символи LaTeX, зберігаючи українську типографіку.

    Деванагарі немає в DejaVu Serif, тому кожен відрізок деванагарі
    обгортається в групу з \\fontspec{...}: інакше XeTeX друкує
    «Missing character» і PDF виходить із дірами замість цитати
    першоджерела. Шрифт ставить CI (пакет fonts-lohit-deva).
    """
    out = []
    for ch in text:
        out.append(SPECIAL.get(ch, ch))
    return DEVA_RUN.sub(
        lambda m: r"{\fontspec[Script=Devanagari]{Lohit Devanagari} "
        + m.group(0) + "}",
        "".join(out),
    )


def load_cards(chapters: tuple[int, ...]) -> list[dict]:
    picked = []
    for path in sorted(CARDS.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        ident = data.get("id", "")
        try:
            chapter = int(str(ident).split(".")[0])
        except (ValueError, IndexError):
            continue
        if chapter in chapters:
            picked.append(data)
    picked.sort(key=lambda d: tuple(int(p) for p in str(d["id"]).split(".")))
    return picked


def load_glossary() -> list[tuple[str, str, str]]:
    if not GLOSSARY.is_file():
        return []
    rows = []
    for line in GLOSSARY.read_text(encoding="utf-8").split("\n"):
        line = line.strip()
        if not line.startswith("|") or line.startswith("|---") or line.startswith("| Термін"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 3:
            rows.append((cells[0], cells[1], cells[2]))
    return rows


def index_hits(text: str, terms: list[str]) -> list[str]:
    hits = []
    for term in terms:
        pattern = (
            r"(?<![\w\u1e00-\u1eff])" + re.escape(term) + r"(?![\w\u1e00-\u1eff])"
        )
        if re.search(pattern, text):
            hits.append(term)
    return hits


def index_entry(term: str) -> str:
    key = term.translate(SORT_MAP).lower()
    return r"\index{%s@\textit{%s}}" % (esc(key), esc(term))


def verse_block(card: dict, terms: list[str]) -> str:
    ident = card.get("id", "?")
    parts = [r"\verseblock{%s}" % esc(str(ident))]
    for field, label in (
        ("ukrainian_translation", "Переклад"),
        ("literal_meaning", "Дослівний сенс"),
        ("grammar", "Граматика"),
        ("commentary", "Коментар"),
    ):
        value = (card.get(field) or "").strip()
        if not value:
            continue
        parts.append(r"\verse%s{%s}" % (label.capitalize(), esc(value)))
    entries = "".join(index_entry(t) for t in index_hits(json.dumps(card, ensure_ascii=False), terms))
    return entries + "\n" + "\n".join(parts) + "\n"


def render(cards: list[dict], glossary: list[tuple[str, str, str]]) -> str:
    terms = [row[0] for row in glossary] + list(INDEX_TERMS)
    seen, unique = set(), []
    for t in terms:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    out = ["% Згенеровано scripts/build_pilot_book.py — не редагувати вручну.", ""]
    current = None
    for card in cards:
        chapter = int(str(card["id"]).split(".")[0])
        if chapter != current:
            out.append(r"\pilotchapter{%d}" % chapter)
            current = chapter
        out.append(verse_block(card, unique))
    return "\n".join(out) + "\n"


def render_glossary(glossary: list[tuple[str, str, str]]) -> str:
    lines = ["% Згенеровано scripts/build_pilot_book.py — не редагувати вручну.", ""]
    for term, translit, meaning in glossary:
        lines.append(
            r"\glossaryrow{%s}{%s}{%s}"
            % (esc(term), esc(translit), esc(meaning))
        )
    return "\n".join(lines) + "\n"


def stale(path: Path, text: str) -> bool:
    return not path.is_file() or path.read_text(encoding="utf-8") != text


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    cards = load_cards(PILOT_CHAPTERS)
    glossary = load_glossary()
    verses = render(cards, glossary)
    gl = render_glossary(glossary)

    targets = {
        BOOK / "generated" / "verses.tex": verses,
        BOOK / "generated" / "glossary.tex": gl,
    }

    outdated = [str(p.relative_to(ROOT)) for p, text in targets.items() if stale(p, text)]

    if args.check:
        print(json.dumps({
            "chapters": list(PILOT_CHAPTERS),
            "cards": len(cards),
            "glossary_terms": len(glossary),
            "generated_chars": len(verses),
            "outdated_before_write": outdated,
        }, ensure_ascii=False, indent=2))
        return 1 if outdated else 0

    for path, text in targets.items():
        write(path, text)

    print(json.dumps({
        "chapters": list(PILOT_CHAPTERS),
        "cards": len(cards),
        "glossary_terms": len(glossary),
        "generated_chars": len(verses),
        "outdated_before_write": outdated,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
