#!/usr/bin/env python3
"""Збирає LaTeX-верстку пілотного видання з власних редакторських карток.

Це не книжковий текст і не переклад «Аштавакра-ґіти». Скрипт бере **наші власні**
поля карток (`editorial/cards/*.json`) — український переклад, дослівне значення,
граматичний розбір, коментар і власні примітки про різночитання — і складає з них
`books/ashtavakra-hita-pilot/generated/verses.tex`.

Читань цифрових свідків (поля `sanskrit` і `iast`) скрипт **не** переносить:
транскрипції GRETIL і SARIT мають власні умови, а паспорт джерела дозволяє PDF
лише для нашого власного внеску. Див. `docs/VYDAVNYCHYI_VYSNOVOK.md`.

Скрипт використовує тільки стандартну бібліотеку, не робить мережевих запитів
і дає побайтово однаковий результат на однакових вхідних даних.
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
# Станом на 2026-11-01 це всі 20 глав: 298 віршів із 298, прогалин немає
# (перевірка: scripts/check_verse_gaps.py --strict).
# Попередня редакція містила 14 глав, бо 1, 15, 16, 17, 18 і 20 тоді
# не мали повного покриття.
PILOT_CHAPTERS = tuple(range(1, 21))

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
    if not CARDS.is_dir():
        raise SystemExit(f"Немає каталогу карток: {CARDS}")
    picked: list[dict] = []
    for path in sorted(CARDS.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        ident = str(data.get("id", ""))
        if "." not in ident:
            continue
        chapter = int(ident.split(".", 1)[0])
        if chapter in chapters:
            picked.append(data)
    picked.sort(key=lambda d: (int(d["id"].split(".")[0]), int(d["id"].split(".")[1])))
    return picked


def load_glossary() -> list[tuple[str, str, str]]:
    """Читає таблицю редакційного словника: санскрит, відповідник, застереження."""
    if not GLOSSARY.is_file():
        return []
    rows: list[tuple[str, str, str]] = []
    for line in GLOSSARY.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 3 or set(cells[0]) <= set("-: "):
            continue
        sanskrit = cells[0].strip("*").strip()
        if not sanskrit or sanskrit.casefold() == "санскрит":
            continue
        rows.append((sanskrit, cells[1], cells[2]))
    return rows


def index_hits(text: str, terms: list[str]) -> list[str]:
    """Терміни покажчика, що справді трапляються в нашому тексті."""
    hits = []
    for term in terms:
        if re.search(
            r"(?<![\w\u1e00-\u1eff])" + re.escape(term) + r"(?![\w\u1e00-\u1eff])",
            text,
        ):
            hits.append(term)
    return hits


def index_entry(term: str) -> str:
    """Запис покажчика з латинським ключем сортування."""
    key = term.translate(SORT_MAP)
    return r"\index{%s@\textit{%s}}" % (esc(key), esc(term))


def verse_block(card: dict, terms: list[str]) -> str:
    ident = card["id"]
    body = " ".join(str(card.get(f) or "") for f in OWN_FIELDS)
    entries = "".join(index_entry(t) for t in index_hits(body, terms))
    parts = [
        r"\virs{%s}{%s}" % (
            esc(ident),
            esc(str(card.get("ukrainian_translation") or "")),
        ),
        r"\virlit{%s}" % esc(str(card.get("literal_meaning") or "")),
        r"\virgram{%s}" % esc(str(card.get("grammar") or "")),
        r"\vircom{%s}" % esc(str(card.get("commentary") or "")),
    ]
    variants = card.get("variants") or []
    if variants:
        notes = []
        for variant in variants:
            witness = esc(str(variant.get("witness") or ""))
            note = esc(str(variant.get("note") or ""))
            notes.append(r"\virvaritem{%s}{%s}" % (witness, note))
        parts.append(r"\virvars{%s}" % "".join(notes))
    else:
        checked = card.get("variants_checked")
        label = (
            "власних приміток про різночитання немає; звіряння свідків позначене як виконане"
            if checked
            else "власних приміток про різночитання немає; звіряння свідків **не** позначене як виконане"
        )
        parts.append(r"\virvarnone{%s}" % esc(label.replace("**", "")))
    gretil = (card.get("sources") or {}).get("gretil") or {}
    sarit = (card.get("sources") or {}).get("sarit") or {}
    parts.append(
        r"\virsources{%s}{%s}"
        % (esc(str(gretil.get("locator") or "—")), esc(str(sarit.get("locator") or "—")))
    )
    return entries + "\n" + "\n".join(parts) + "\n"


def render(cards: list[dict], glossary: list[tuple[str, str, str]]) -> str:
    terms = list(INDEX_TERMS) + [row[0] for row in glossary if row[0] not in INDEX_TERMS]
    out: list[str] = [
        "% ЗГЕНЕРОВАНО scripts/build_pilot_book.py — не редагувати вручну.",
        "% Джерело: editorial/cards/*.json, глави "
        + ", ".join(str(c) for c in PILOT_CHAPTERS)
        + ".",
        "% Містить лише власні поля карток: переклад, дослівне значення,",
        "% граматичний розбір, коментар, примітки про різночитання.",
        "",
    ]
    by_chapter: dict[int, list[dict]] = {}
    for card in cards:
        by_chapter.setdefault(int(card["id"].split(".")[0]), []).append(card)

    for chapter in sorted(by_chapter):
        out.append(r"\pilotchapter{%d}{%d}" % (chapter, len(by_chapter[chapter])))
        for card in by_chapter[chapter]:
            out.append(verse_block(card, terms))
    return "\n".join(out) + "\n"


def render_glossary(glossary: list[tuple[str, str, str]]) -> str:
    lines = [
        "% ЗГЕНЕРОВАНО scripts/build_pilot_book.py — не редагувати вручну.",
        r"\begin{longtable}{@{}p{0.20\textwidth}p{0.30\textwidth}p{0.40\textwidth}@{}}",
        r"\textbf{\sffamily Санскрит} & \textbf{\sffamily Робочий відповідник} & "
        r"\textbf{\sffamily Застереження} \\",
        r"\hline",
        r"\endhead",
    ]
    for sanskrit, ukrainian, caveat in glossary:
        lines.append(
            r"\textit{%s} & %s & %s \\" % (esc(sanskrit), esc(ukrainian), esc(caveat))
        )
    lines.append(r"\end{longtable}")
    return "\n".join(lines) + "\n"


def stale(path: Path, text: str) -> bool:
    """Чи відрізняється наявний файл від згенерованого вмісту."""
    return not path.is_file() or path.read_text(encoding="utf-8") != text


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="не писати, лише перевірити, чи згенероване актуальне")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    cards = load_cards(PILOT_CHAPTERS)
    glossary = load_glossary()
    if not cards:
        print("Карток для пілота не знайдено.", file=sys.stderr)
        return 1

    for card in cards:
        missing = [f for f in OWN_FIELDS if not card.get(f)]
        if missing:
            print(f"Картка {card['id']}: порожні власні поля {missing}", file=sys.stderr)
            return 1
        if card.get("status") != "чернетка":
            print(f"Картка {card['id']}: неочікуваний статус {card.get('status')}",
                  file=sys.stderr)
            return 1

    verses = render(cards, glossary)
    words = render_glossary(glossary)
    verses_path = BOOK / "generated" / "verses.tex"
    glossary_path = BOOK / "generated" / "glossary.tex"
    outdated = [
        str(p.relative_to(BOOK))
        for p, text in ((verses_path, verses), (glossary_path, words))
        if stale(p, text)
    ]

    manifest = {
        "chapters": list(PILOT_CHAPTERS),
        "verses": len(cards),
        "cards": [c["id"] for c in cards],
        "statuses": sorted({c["status"] for c in cards}),
        "witness_fields_excluded": list(WITNESS_FIELDS),
        "glossary_terms": len(glossary),
        "generated_chars": len(verses) + len(words),
        "outdated_before_write": outdated,
    }
    payload = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"

    if not args.check:
        write(verses_path, verses)
        write(glossary_path, words)
        write(BOOK / "generated" / "manifest.json", payload)
    print(payload, end="")

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload, encoding="utf-8")

    if args.check and outdated:
        print("Згенеровані файли застаріли: " + ", ".join(outdated), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
